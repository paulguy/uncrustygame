#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "tilemap.h"

typedef struct {
    PyTypeObject *CrustyException;
    PyTypeObject *LayerListType;

    /* types needed type type checking */
    PyTypeObject *LP_SDL_Renderer;
    PyTypeObject *LP_SDL_Texture;
} crustygame_state;

typedef struct {
    PyObject_HEAD
    LayerList *ll;
    PyObject *log_cb;
    PyObject *log_priv;
    PyObject *renderer;
} LayerListObject;

static PyObject *get_from_dict_string(PyObject *from, const char *str) {
    PyObject *pystr;
    PyObject *obj;

    pystr = PyUnicode_FromString(str);
    obj = PyDict_GetItem(from, pystr);
    Py_DECREF(pystr);
    if(obj == NULL) {
        return(NULL);
    }

    return(obj);
}

static PyTypeObject *get_symbol_from_string(PyObject *m, const char *str) {
    PyObject *moddict = PyModule_GetDict(m);
    if(moddict == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "couldn't get dict for module");
        return(NULL);
    }

    PyObject *typeobj = get_from_dict_string(moddict, str);
    if(typeobj == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "couldn't get type from module dict");
        return(NULL);
    }

    return(typeobj);
}

static void log_cb_adapter(LayerListObject *self, const char *str) {
    PyObject *arglist;
    PyObject *result;

    arglist = Py_BuildValue("sO", str, self->log_priv);
    result = PyObject_CallObject(self->log_cb, arglist);
    Py_DECREF(arglist);
    /* don't check the result because this is called by C code anyway and it
     * is void */
    Py_XDECREF(result);
}

static PyObject *LayerList_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {
    LayerListObject *self;

    self = (LayerListObject *)type->tp_alloc(type, 0);
    if(self == NULL) {
        return(NULL);
    }
    /* just have it be do-nothing until it's properly initialize */
    self->ll = NULL;

    return(self);
}

static int LayerList_init(LayerListObject *self, PyObject *args, PyObject *kwds) {
    PyObject *renderer;
    unsigned int format;
    PyObject *log_cb;
    PyObject *log_priv;
    /* docs say this init isn't called if the class is instantiated as some
     * other type.  Not sure the consequences there... */
    crustygame_state *state = PyType_GetModuleState(Py_TYPE(self));

    if(!PyArg_ParseTuple(args, "OIOO", &renderer, &format, &log_cb, &log_priv)) {
        return(-1);
    }

    if(self->ll != NULL) {
        PyErr_SetString(PyExc_TypeError, "LayerList already initialized");
        return(-1);
    }

    if(!PyObject_TypeCheck(renderer, state->LP_SDL_Renderer)) {
        PyErr_SetString(PyExc_TypeError, "got something not an SDL_Renderer");
        return(-1);
    }
    if(!PyCallable_Check(log_cb)) {
        PyErr_SetString(PyExc_TypeError, "log_cb must be callable");
        return(-1);
    }
    Py_XINCREF(renderer);
    Py_XINCREF(log_cb);
    Py_XINCREF(log_priv);

    self->ll = layerlist_new(renderer, format, log_cb_adapter, self);
    if(self->ll == NULL) {
        PyErr_SetString(state->CrustyException, "layerlist_new returned an error");
        Py_XDECREF(log_priv);
        Py_XDECREF(log_cb);
        Py_XDECREF(renderer);
    }

    self->log_cb = log_cb;
    self->log_priv = log_priv;
    self->renderer = renderer;

    return(0);
}

static void LayerList_dealloc(LayerListObject *self) {
    if(self->ll != NULL) {
        layerlist_free(self->ll);
        Py_XDECREF(self->log_priv);
        Py_XDECREF(self->log_cb);
        Py_XDECREF(self->renderer);
    }
    Py_TYPE(self)->tp_free((PyObject *) self);
}

static PyObject *LayerList_set_default_render_target(PyObject *self,
                                                     PyTypeObject *defining_class,
                                                     PyObject *const *args,
                                                     Py_ssize_t nargs,
                                                     PyObject *kwnames) {
    LayerListObject *ll = self;
    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    PyObject *target = args[0];

    if(target == Py_None) {
        target = NULL;
    } else {
        if(!PyObject_TypeCheck(target, state->LP_SDL_Texture)) {
            PyErr_SetString(PyExc_TypeError, "render target must be a SDL_Texture.");
            return(NULL);
        }
    }

    tilemap_set_default_render_target(ll->ll, target);

    Py_RETURN_NONE;
}

static PyObject *LayerList_set_target_tileset(PyObject *self,
                                              PyTypeObject *defining_class,
                                              PyObject *const *args,
                                              Py_ssize_t nargs,
                                              PyObject *kwnames) {
    long tileset;
    int retval;
    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    tileset = PyLong_AsLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    LayerListObject *ll = self;
    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(tilemap_set_target_tileset(ll->ll, (int)tileset)) {
        PyErr_SetString(state->CrustyException, "Couldn't set target tileset.");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyMethodDef LayerList_methods[] = {
    {
        "set_default_render_target",
        (PyCMethod) LayerList_set_default_render_target,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the default texture to render to.  Isn't applied immediately, though."},
    {
        "set_target_tileset",
        (PyCMethod) LayerList_set_target_tileset,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the tileset to render to or the default render target if less than 0."},
    {NULL}
};

static int LayerList_getrenderer(LayerListObject *self, PyObject *value, void *closure) {
    /* don't bother calling the original method, since the object holds its own
     * copy */
    /* I think the reference count needs to be increased?  I think when the
     * calling functions returns it'll be decremented?  So i guess prevent it
     * from being deleted? */
    Py_INCREF(self->renderer);
    return(self->renderer);
}

static PyGetSetDef LayerList_getsetters[] = {
    {"renderer", (getter) LayerList_getrenderer, NULL, "Get the renderer back from the LayerList."},
    {NULL}
};

/* needed because it's a heap type, i guess */
static int LayerList_traverse(PyObject *self, visitproc visit, void *arg) {
    Py_VISIT(Py_TYPE(self));
    return 0;
}

static PyType_Slot LayerListSlots[] = {
    {Py_tp_new, LayerList_new},
    {Py_tp_init, (initproc)LayerList_init},
    {Py_tp_dealloc, (destructor)LayerList_dealloc},
    {Py_tp_methods, LayerList_methods},
    {Py_tp_getset, LayerList_getsetters},
    {Py_tp_traverse, LayerList_traverse},
    {0, NULL}
};

static PyType_Spec LayerListSpec = {
    .name = "crustygame.LayerList",
    .basicsize = sizeof(LayerListObject),
    .itemsize = 0,
    .flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .slots = LayerListSlots
};

int crustygame_exec(PyObject* m) {
    fprintf(stderr, "exec\n");
    crustygame_state *state = PyModule_GetState(m);
    PyObject *ctypes_m;
    PyObject *ctypes_POINTER;
    PyObject *SDL_m;
    PyObject *SDL_Renderer_t;
    PyObject *SDL_Texture_t;

    state->CrustyException = PyErr_NewException("crustygame.CrustyException", NULL, NULL);
    if (PyModule_AddObject(m, "CrustyException", state->CrustyException) < 0) {
        Py_DECREF(state->CrustyException);
        return(-1);
    }

    state->LayerListType = PyType_FromModuleAndSpec(m, &LayerListSpec, NULL);
    if(PyModule_AddObject(m, "LayerList", (PyObject *)state->LayerListType) < 0) {
        Py_DECREF(state->LayerListType);
        Py_DECREF(state->CrustyException);
        return(-1);
    }

    /* Generate an LP_SDL_Renderer to compare with for type validation later on
     * so weirdness can't happen if oddball types are passed in */
    ctypes_m = PyImport_ImportModule("ctypes");
    if(ctypes_m == NULL) {
        Py_DECREF(state->LayerListType);
        Py_DECREF(state->CrustyException);
        return(-1);
    }
    ctypes_POINTER = get_symbol_from_string(ctypes_m, "POINTER");
    Py_XINCREF(ctypes_POINTER);
    if(ctypes_POINTER == NULL) {
        Py_DECREF(ctypes_m);
        Py_DECREF(state->LayerListType);
        Py_DECREF(state->CrustyException);
        return(-1);
    }

    SDL_m = PyImport_ImportModule("sdl2");
    if(SDL_m == NULL) {
        Py_DECREF(ctypes_POINTER);
        Py_DECREF(ctypes_m);
        Py_DECREF(state->LayerListType);
        Py_DECREF(state->CrustyException);
        return(-1);
    }

    SDL_Renderer_t = get_symbol_from_string(SDL_m, "SDL_Renderer");
    Py_XINCREF(SDL_Renderer_t);
    if(SDL_Renderer_t == NULL) {
        Py_DECREF(SDL_m);
        Py_DECREF(ctypes_POINTER);
        Py_DECREF(ctypes_m);
        Py_DECREF(state->LayerListType);
        Py_DECREF(state->CrustyException);
        return(-1);
    }
    state->LP_SDL_Renderer = PyObject_CallOneArg(ctypes_POINTER, SDL_Renderer_t);
    if(state->LP_SDL_Renderer == NULL) {
        Py_DECREF(SDL_Renderer_t);
        Py_DECREF(SDL_m);
        Py_DECREF(ctypes_POINTER);
        Py_DECREF(ctypes_m);
        Py_DECREF(state->LayerListType);
        Py_DECREF(state->CrustyException);
        return(-1);
    }

    SDL_Texture_t = get_symbol_from_string(SDL_m, "SDL_Texture");
    Py_XINCREF(SDL_Texture_t);
    if(SDL_Texture_t == NULL) {
        Py_DECREF(state->LP_SDL_Renderer);
        Py_DECREF(SDL_Renderer_t);
        Py_DECREF(SDL_m);
        Py_DECREF(ctypes_POINTER);
        Py_DECREF(ctypes_m);
        Py_DECREF(state->LayerListType);
        Py_DECREF(state->CrustyException);
        return(-1);
    }
    state->LP_SDL_Texture = PyObject_CallOneArg(ctypes_POINTER, SDL_Texture_t);
    if(state->LP_SDL_Texture == NULL) {
        Py_DECREF(SDL_Texture_t);
        Py_DECREF(state->LP_SDL_Renderer);
        Py_DECREF(SDL_Renderer_t);
        Py_DECREF(SDL_m);
        Py_DECREF(ctypes_POINTER);
        Py_DECREF(ctypes_m);
        Py_DECREF(state->LayerListType);
        Py_DECREF(state->CrustyException);
        return(-1);
    }

    Py_DECREF(SDL_Texture_t);
    Py_DECREF(SDL_Renderer_t);
    Py_DECREF(SDL_m);
    Py_DECREF(ctypes_POINTER);
    Py_DECREF(ctypes_m);
    return(0);
}

static void crustygame_free(void *p) {
    crustygame_state *state = PyModule_GetState((PyObject *)p);
    Py_DECREF(state->LP_SDL_Texture);
    Py_DECREF(state->LP_SDL_Renderer);
    Py_DECREF(state->LayerListType);
    Py_DECREF(state->CrustyException);
    PyObject_Free(p);
}

static struct PyModuleDef_Slot crustygamemodule_slots[] = {
    {Py_mod_exec, crustygame_exec},
    {0, NULL}
};

static struct PyModuleDef crustygamemodule = {
    PyModuleDef_HEAD_INIT,
    .m_name = "crustygame",
    .m_doc = NULL,
    .m_size = sizeof(crustygame_state),
    .m_slots = crustygamemodule_slots,
    .m_free = (freefunc)crustygame_free
};

PyMODINIT_FUNC PyInit_crustygame(void) {
    fprintf(stderr, "PyInit\n");
    return(PyModuleDef_Init(&crustygamemodule));
}
