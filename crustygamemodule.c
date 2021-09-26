#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "tilemap.h"

typedef struct {
    PyObject *CrustyException;
    PyTypeObject *LayerListType;
    PyTypeObject *TilesetType;

    /* types needed type type checking */
    PyTypeObject *LP_SDL_Renderer;
    PyTypeObject *LP_SDL_Texture;
    PyTypeObject *LP_SDL_Surface;
} crustygame_state;

typedef struct {
    PyObject_HEAD
    LayerList *ll;
    PyObject *log_cb;
    PyObject *log_priv;
    PyObject *renderer;
} LayerListObject;

typedef struct {
    PyObject_HEAD
    LayerListObject *ll;
    unsigned int tileset;
} TilesetObject;

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

/* this using function above it are helpful in getting a symbol provided as a
 * string from a module. */
static PyObject *get_symbol_from_string(PyObject *m, const char *str) {
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

/* used for unwrapping the real log_cb and log_priv and calling the
 * user-supplied callable, on behalf of the generic C-side function which calls
 * this method */
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

/* documentation says it's needed for heap allocated types */
static int heap_type_traverse(PyObject *self, visitproc visit, void *arg) {
    Py_VISIT(Py_TYPE(self));
    return 0;
}

static PyObject *LayerList_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {
    LayerListObject *self;

    self = (LayerListObject *)type->tp_alloc(type, 0);
    if(self == NULL) {
        return(NULL);
    }
    /* just have it be do-nothing until it's properly initialize */
    self->ll = NULL;

    return((PyObject *)self);
}

static int LayerList_init(LayerListObject *self, PyObject *args, PyObject *kwds) {
    unsigned int format;

    if(self->ll != NULL) {
        PyErr_SetString(PyExc_TypeError, "LayerList already initialized");
        return(-1);
    }

    /* docs say this init isn't called if the class is instantiated as some
     * other type.  Not sure the consequences there... */
    crustygame_state *state = PyType_GetModuleState(Py_TYPE(self));

    if(!PyArg_ParseTuple(args, "OIOO",
                         &(self->renderer),
                         &format,
                         &(self->log_cb),
                         &(self->log_priv))) {
        return(-1);
    }
    Py_XINCREF(self->renderer);
    Py_XINCREF(self->log_cb);
    Py_XINCREF(self->log_priv);

    if(!PyObject_TypeCheck(self->renderer, state->LP_SDL_Renderer)) {
        PyErr_SetString(PyExc_TypeError, "got something not an SDL_Renderer");
        goto error;
    }
    if(!PyCallable_Check(self->log_cb)) {
        PyErr_SetString(PyExc_TypeError, "log_cb must be callable");
        goto error;
    }
    /* LP_SDL_Renderer is literally just a pointer to an SDL_Renderer, so this
     * works directly casting from PyObject *. */
    self->ll = layerlist_new((SDL_Renderer *)(self->renderer),
                             format,
                             (log_cb_return_t)log_cb_adapter,
                             self);
    if(self->ll == NULL) {
        PyErr_SetString(state->CrustyException, "layerlist_new returned an error");
        goto error;
    }

    return(0);

error:
    Py_CLEAR(self->log_priv);
    Py_CLEAR(self->log_cb);
    Py_CLEAR(self->renderer);
    return(-1);
}

static void LayerList_dealloc(LayerListObject *self) {
    if(self->ll != NULL) {
        layerlist_free(self->ll);
    }
    Py_XDECREF(self->log_priv);
    Py_XDECREF(self->log_cb);
    Py_XDECREF(self->renderer);
    Py_TYPE(self)->tp_free((PyObject *) self);
}

/* member functions which need to do type checking by accessing the types held
 * in the module state need to use the rather new as of 3.9 PyCMethod function
 * members of the type as this is the only one which provides the _real_ type
 * and guarantees GetModuleState will actually return the state of the defining
 * class. */
static PyObject *LayerList_set_default_render_target(LayerListObject *self,
                                                     PyTypeObject *defining_class,
                                                     PyObject *const *args,
                                                     Py_ssize_t nargs,
                                                     PyObject *kwnames) {
    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this LayerList is not initialized");
        return(NULL);
    }

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

    /* as above, the cast to SDL_Texture works because python type
     * LP_SDL_Texture is just literally the same as a pointer to a
     * SDL_Texture *. */
    tilemap_set_default_render_target(self->ll, (SDL_Texture *)target);

    Py_RETURN_NONE;
}

static PyObject *LayerList_set_target_tileset(LayerListObject *self,
                                              PyTypeObject *defining_class,
                                              PyObject *const *args,
                                              Py_ssize_t nargs,
                                              PyObject *kwnames) {
    long tileset;

    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this LayerList is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    tileset = PyLong_AsLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    if(tilemap_set_target_tileset(self->ll, (int)tileset)) {
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

static PyObject *LayerList_getrenderer(LayerListObject *self, void *closure) {
    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this LayerList is not initialized");
        return(NULL);
    }

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

/* Needed for heap-based type instantiation.  Hopefully future proof for this
 * project.  Its benefits seem worth the bit of extra complexity. */
static PyType_Slot LayerListSlots[] = {
    {Py_tp_new, LayerList_new},
    {Py_tp_init, (initproc)LayerList_init},
    {Py_tp_dealloc, (destructor)LayerList_dealloc},
    {Py_tp_methods, LayerList_methods},
    {Py_tp_getset, LayerList_getsetters},
    {Py_tp_traverse, heap_type_traverse},
    {0, NULL}
};

static PyType_Spec LayerListSpec = {
    .name = "crustygame.LayerList",
    .basicsize = sizeof(LayerListObject),
    .itemsize = 0,
    .flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .slots = LayerListSlots
};

static PyObject *Tileset_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {
    TilesetObject *self;

    self = (TilesetObject *)type->tp_alloc(type, 0);
    if(self == NULL) {
        return(NULL);
    }
    self->ll = NULL;
    self->tileset = -1;
 
    return((PyObject *)self);
}

static int Tileset_init(TilesetObject *self, PyObject *args, PyObject *kwds) {
    unsigned int tw, th;
    unsigned int w, h;
    unsigned int color;
    const char *filename;
    PyObject *surface;
    PyObject *etype, *evalue, *etraceback;

    if(self->ll != NULL) {
        PyErr_SetString(PyExc_TypeError, "Tileset already initialized");
        return(-1);
    }

    crustygame_state *state = PyType_GetModuleState(Py_TYPE(self));

    /* first try to see if a blank tileset is requested, as it has the most
     * number of arguments and would definitely fail if the wrong amount of
     * arguments was provided */
    if(!PyArg_ParseTuple(args, "OIIIII",
                         &self->ll, &w, &h, &color, &tw, &th)) {
        PyErr_Fetch(&etype, &evalue, &etraceback);
        /* don't care too much to inspect what went wrong, just try something
         * else anyway */
        Py_XDECREF(etype);
        Py_XDECREF(evalue);
        Py_XDECREF(etraceback);
    } else {
        Py_XINCREF(self->ll);
        if(!PyObject_TypeCheck(self->ll, state->LayerListType)) {
            PyErr_SetString(PyExc_TypeError, "first argument must be a LayerListType");
            goto error;
        }

        self->tileset = tilemap_blank_tileset(self->ll->ll, w, h, color, tw, th);
        if(self->tileset < 0) {
            PyErr_SetString(state->CrustyException, "tilemap_blank_tileset failed");
            goto error;
        }

        return(0);
    }

    /* now check if a string is provided, and if so use it as a filename */
    if(!PyArg_ParseTuple(args, "OsII",
                         &self->ll, &filename, &tw, &th)) {
        PyErr_Fetch(&etype, &evalue, &etraceback);
        Py_XDECREF(etype);
        Py_XDECREF(evalue);
        Py_XDECREF(etraceback);
    } else {
        Py_XINCREF(self->ll);
        if(!PyObject_TypeCheck(self->ll, state->LayerListType)) {
            PyErr_SetString(PyExc_TypeError, "first argument must be a LayerListType");
            goto error;
        }

        self->tileset = tilemap_tileset_from_bmp(self->ll->ll,
                                                 filename,
                                                 tw, th);
        if(self->tileset < 0) {
            PyErr_SetString(state->CrustyException, "tilemap_tileset_from_bmp failed");
            goto error;
        }

        return(0);
    }

    /* now check to see if an SDL_Surface is provided, do this last because one
     * hopes SDL_Surface can't be made in to a string, and the first one would
     * succeed, where this one can't be first because it'd catch any object
     * then fail anyway */
    if(!PyArg_ParseTuple(args, "OOII",
                         &self->ll, &surface, &tw, &th)) {
        PyErr_Fetch(&etype, &evalue, &etraceback);
        Py_XDECREF(etype);
        Py_XDECREF(evalue);
        Py_XDECREF(etraceback);
    } else {
        Py_XINCREF(self->ll);
        Py_XINCREF(surface);
        if(!PyObject_TypeCheck(self->ll, state->LayerListType)) {
            PyErr_SetString(PyExc_TypeError, "first argument must be a LayerListType");
            goto error;
        }
        if(!PyObject_TypeCheck(surface, state->LP_SDL_Surface)) {
            PyErr_SetString(PyExc_TypeError, "second argument must be a SDL_Surface");
            goto error;
        }

        self->tileset = tilemap_add_tileset(self->ll->ll,
                                            (SDL_Surface *)surface,
                                            tw, th);
        if(self->tileset < 0) {
            PyErr_SetString(state->CrustyException, "tilemap_add_tileset failed");
            goto error;
        }
        Py_XDECREF(surface);

        return(0);
    }

    /* fell through, so just set a generic error that everything failed */
    PyErr_SetString(PyExc_TypeError, "invalid arguments for tileset creation");

error:
    Py_XDECREF(surface);
    Py_CLEAR(self->ll);
    return(-1);
}

static void Tileset_dealloc(TilesetObject *self) {
    if(self->tileset >= 0) {
        tilemap_free_tileset(self->ll->ll, self->tileset);
    }
    Py_XDECREF(self->ll);
    Py_TYPE(self)->tp_free((PyObject *) self);
}

static PyType_Slot TilesetSlots[] = {
    {Py_tp_new, Tileset_new},
    {Py_tp_init, (initproc)Tileset_init},
    {Py_tp_dealloc, (destructor)Tileset_dealloc},
    {Py_tp_traverse, heap_type_traverse},
    {0, NULL}
};

static PyType_Spec TilesetSpec = {
    .name = "crustygame.Tileset",
    .basicsize = sizeof(TilesetObject),
    .itemsize = 0,
    .flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .slots = TilesetSlots
};

/* objects successfully returned by this function automatically have a new
 * reference because objects returned by the various PyObject_Call* functions
 * return with a new reference. */
static PyTypeObject *get_literal_pointer_type(PyObject *module,
                                              PyObject *POINTER,
                                              const char *str) {
    PyObject *type = get_symbol_from_string(module, str);
    if(type == NULL) {
        return(NULL);
    }
    PyObject *lptype = PyObject_CallOneArg(POINTER, type);
    if(lptype == NULL) {
        return(NULL);
    }

    return((PyTypeObject *)lptype);
}

static int crustygame_exec(PyObject* m) {
    crustygame_state *state = PyModule_GetState(m);
    /* set all to NULL so a line up Py_XDECREF() will just skip over what's not
     * been referenced, yet */
    state->CrustyException = NULL;
    state->LayerListType = NULL;
    state->LP_SDL_Renderer = NULL;
    state->LP_SDL_Texture = NULL;
    state->LP_SDL_Surface = NULL;
    PyObject *ctypes_m = NULL;
    PyObject *ctypes_POINTER = NULL;
    PyObject *SDL_m = NULL;

    /* Make an exception used for problems returned by the library. */
    state->CrustyException = PyErr_NewException("crustygame.CrustyException", NULL, NULL);
    if (PyModule_AddObject(m, "CrustyException", state->CrustyException) < 0) {
        goto error;
    }

    /* heap allocate the new types and store them in the module state */
    state->LayerListType = (PyTypeObject *)PyType_FromModuleAndSpec(m, &LayerListSpec, NULL);
    if(PyModule_AddObject(m, "LayerList", (PyObject *)state->LayerListType) < 0) {
        goto error;
    }
    state->TilesetType = (PyTypeObject *)PyType_FromModuleAndSpec(m, &TilesetSpec, NULL);
    if(PyModule_AddObject(m, "Tileset", (PyObject *)state->TilesetType) < 0) {
        goto error;
    }

    /* import ctypes for its POINTER() method which produces, and importantly
     * internally caches the literal pointer type of a ctypes defined structure
     * which python's sdl2 uses for structs passed around.  This is so types
     * can be checked before possible, difficult to track down crashes may
     * occur and useful error messages can be given to the user. */
    ctypes_m = PyImport_ImportModule("ctypes");
    if(ctypes_m == NULL) {
        goto error;
    }
    ctypes_POINTER = get_symbol_from_string(ctypes_m, "POINTER");
    Py_XINCREF(ctypes_POINTER);
    if(ctypes_POINTER == NULL) {
        goto error;
    }

    /* import sdl2 and get the literal pointer types needed for type checks. */
    SDL_m = PyImport_ImportModule("sdl2");
    if(SDL_m == NULL) {
        goto error;
    }
    state->LP_SDL_Renderer = get_literal_pointer_type(SDL_m, ctypes_POINTER, "SDL_Renderer");
    if(state->LP_SDL_Renderer == NULL) {
        goto error;
    }
    state->LP_SDL_Texture = get_literal_pointer_type(SDL_m, ctypes_POINTER, "SDL_Texture");
    if(state->LP_SDL_Texture == NULL) {
        goto error;
    }
    state->LP_SDL_Surface = get_literal_pointer_type(SDL_m, ctypes_POINTER, "SDL_Surface");
    if(state->LP_SDL_Surface == NULL) {
        goto error;
    }

    Py_DECREF(SDL_m);
    Py_DECREF(ctypes_POINTER);
    Py_DECREF(ctypes_m);
    return(0);

error:
    /* use Py_CLEAR because the free method might be called after this and
     * would erroneously decrease their reference count again if that is the
     * case */
    Py_CLEAR(state->LP_SDL_Surface);
    Py_CLEAR(state->LP_SDL_Texture);
    Py_CLEAR(state->LP_SDL_Renderer);
    Py_XDECREF(SDL_m);
    Py_XDECREF(ctypes_POINTER);
    Py_XDECREF(ctypes_m);
    Py_CLEAR(state->TilesetType);
    Py_CLEAR(state->LayerListType);
    Py_CLEAR(state->CrustyException);
    return(-1);
}

/* This is an oddball module method that I guess isn't in a slot.  Don't know
 * why, or whether it matters? */
static void crustygame_free(void *p) {
    crustygame_state *state = PyModule_GetState((PyObject *)p);
    Py_XDECREF(state->LP_SDL_Surface);
    Py_XDECREF(state->LP_SDL_Texture);
    Py_XDECREF(state->LP_SDL_Renderer);
    Py_XDECREF(state->LayerListType);
    Py_XDECREF(state->CrustyException);
    PyObject_Free(p);
}

/* heap-based module instantiation.  Using this because types in the module
 * state I would assume are going to be different in many cases where there
 * would need to be many instances of the same module? */
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
    return(PyModuleDef_Init(&crustygamemodule));
}
