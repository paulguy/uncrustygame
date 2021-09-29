#include <stdint.h>

#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "tilemap.h"

typedef struct {
    PyObject *CrustyException;
    PyTypeObject *LayerListType;
    PyTypeObject *TilesetType;
    PyTypeObject *TilemapType;
    PyTypeObject *LayerType;

    /* ctypes callable which will point to the function a bit further down */
    PyObject *return_ptr;

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
    /* for the refernce */
    PyObject *py_renderer;
    SDL_Renderer *renderer;
} LayerListObject;

typedef struct {
    PyObject_HEAD
    LayerListObject *ll;
    int tileset;
} TilesetObject;

typedef struct {
    PyObject_HEAD
    LayerListObject *ll;
    TilesetObject *ts;
    int tilemap;
} TilemapObject;

typedef struct {
    PyObject_HEAD
    LayerListObject *ll;
    TilemapObject *tm;
    int layer;
} LayerObject;

/* awful hack function used to get pointers back from a ctypes object */
uintptr_t awful_return_ptr_hack_funct(void *ptr) {
    return((uintptr_t)ptr);
}

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

/* pass a ctype LP_* type object through ctypes and have it return an intptr_t
 * back in and pass that back as a void pointer.  Seems to work, don't know
 * about cross platform compatibility, but this seems to be the only way for
 * this to work. */
/* probably a pretty slow method to call so probably don't do it too often.. */
static void *get_value_from_lp_object(crustygame_state *state,
                                      PyObject *lp_obj) {
    void *ptr;

    PyObject *num = PyObject_CallOneArg(state->return_ptr, lp_obj);
    if(num == NULL) {
        return(NULL);
    }
    ptr = PyLong_AsVoidPtr(num);

    Py_DECREF(num);
    return(ptr);
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
    self->py_renderer = NULL;
    self->log_cb = NULL;
    self->log_priv = NULL;

    if(self->ll != NULL) {
        PyErr_SetString(PyExc_TypeError, "LayerList already initialized");
        return(-1);
    }

    /* docs say this init isn't called if the class is instantiated as some
     * other type.  Not sure the consequences there... */
    crustygame_state *state = PyType_GetModuleState(Py_TYPE(self));

    if(!PyArg_ParseTuple(args, "OIOO",
                         &(self->py_renderer),
                         &format,
                         &(self->log_cb),
                         &(self->log_priv))) {
        return(-1);
    }
    Py_XINCREF(self->py_renderer);
    Py_XINCREF(self->log_cb);
    Py_XINCREF(self->log_priv);

    if(!PyObject_TypeCheck(self->py_renderer, state->LP_SDL_Renderer)) {
        PyErr_SetString(PyExc_TypeError, "got something not an SDL_Renderer");
        goto error;
    }
    if(!PyCallable_Check(self->log_cb)) {
        PyErr_SetString(PyExc_TypeError, "log_cb must be callable");
        goto error;
    }
    self->renderer = (SDL_Renderer *)get_value_from_lp_object(state, self->py_renderer);
    if(self->renderer == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "couldn't get pointer of SDL_Renderer");
        goto error;
    }

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
    Py_CLEAR(self->py_renderer);
    return(-1);
}

static void LayerList_dealloc(LayerListObject *self) {
    if(self->ll != NULL) {
        layerlist_free(self->ll);
    }
    Py_XDECREF(self->log_priv);
    Py_XDECREF(self->log_cb);
    Py_XDECREF(self->py_renderer);
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
    SDL_Texture *target = NULL;

    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this LayerList is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }

    if(args[0] == Py_None) {
        target = NULL;
    } else {
        if(!PyObject_TypeCheck(args[0], state->LP_SDL_Texture)) {
            PyErr_SetString(PyExc_TypeError, "render target must be a SDL_Texture or None.");
            return(NULL);
        }
        target = (SDL_Texture *)get_value_from_lp_object(state, args[0]);
        if(target == NULL) {
            PyErr_SetString(PyExc_RuntimeError, "couldn't get pointer of SDL_Texture");
            return(NULL);
        }
    }

    tilemap_set_default_render_target(self->ll, (SDL_Texture *)target);

    Py_RETURN_NONE;
}

static PyObject *LayerList_set_target_tileset(LayerListObject *self,
                                              PyTypeObject *defining_class,
                                              PyObject *const *args,
                                              Py_ssize_t nargs,
                                              PyObject *kwnames) {
    int target = -1;

    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this LayerList is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }

    if(args[0] == Py_None) {
        target = -1;
    } else {
        if(!PyObject_TypeCheck(args[0], state->TilesetType)) {
            PyErr_SetString(PyExc_TypeError, "render target must be a Tileset or None.");
            return(NULL);
        }
        target = ((TilesetObject *)(args[0]))->tileset;
    }

    if(tilemap_set_target_tileset(self->ll, target) < 0) {
        PyErr_SetString(state->CrustyException, "Couldn't set target tileset.");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *LayerList_LL_Tileset(LayerListObject *self,
                                      PyTypeObject *defining_class,
                                      PyObject *const *args,
                                      Py_ssize_t nargs,
                                      PyObject *kwnames) {
    PyObject *arglist;
    PyObject *tileset;

    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this LayerList is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs == 3) {
        arglist = PyTuple_Pack(4, self, args[0], args[1], args[2]);
    } else if(nargs == 5) {
        arglist = PyTuple_Pack(6, self, args[0], args[1], args[2], args[3], args[4]);
    } else {
        PyErr_SetString(PyExc_TypeError, "this function needs 3 or 5 arguments");
        return(NULL);
    }

    if(arglist == NULL) {
        return(NULL);
    }
    tileset = PyObject_CallObject(state->TilesetType, arglist);
    Py_DECREF(arglist);
    if(tileset == NULL) {
        return(NULL);
    }
    return(tileset);
}

static PyObject *LayerList_LL_Tilemap(LayerListObject *self,
                                      PyTypeObject *defining_class,
                                      PyObject *const *args,
                                      Py_ssize_t nargs,
                                      PyObject *kwnames) {
    PyObject *arglist;
    PyObject *tilemap;

    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this LayerList is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 3) {
        PyErr_SetString(PyExc_TypeError, "this function needs 3 arguments");
        return(NULL);
    }

    arglist = PyTuple_Pack(4, self, args[0], args[1], args[2]);
    if(arglist == NULL) {
        return(NULL);
    }
    tilemap = PyObject_CallObject(state->TilemapType, arglist);
    Py_DECREF(arglist);
    if(tilemap == NULL) {
        return(NULL);
    }

    return(tilemap);
}

static PyMethodDef LayerList_methods[] = {
    {
        "default_render_target",
        (PyCMethod) LayerList_set_default_render_target,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the default texture to render to.  Isn't applied immediately, though."},
    {
        "target_tileset",
        (PyCMethod) LayerList_set_target_tileset,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the tileset to render to or the default render target if less than 0."},
    {
        "Tileset",
        (PyCMethod) LayerList_LL_Tileset,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Convenience method to create a Tileset from this LayerList."},
    {
        "Tilemap",
        (PyCMethod) LayerList_LL_Tilemap,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Convenience method to create a Tilemap from this LayerList."},
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
    Py_INCREF(self->py_renderer);
    return(self->py_renderer);
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
    PyObject *py_surface = NULL;
    SDL_Surface *surface = NULL;
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
                         &(self->ll), &w, &h, &color, &tw, &th)) {
        PyErr_Fetch(&etype, &evalue, &etraceback);
        /* don't care too much to inspect what went wrong, just try something
         * else anyway */
        Py_XDECREF(etype);
        Py_XDECREF(evalue);
        Py_XDECREF(etraceback);
    } else {
        Py_XINCREF(self->ll);
        if(!PyObject_TypeCheck(self->ll, state->LayerListType)) {
            PyErr_SetString(PyExc_TypeError, "first argument must be a LayerList");
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
                         &(self->ll), &filename, &tw, &th)) {
        PyErr_Fetch(&etype, &evalue, &etraceback);
        Py_XDECREF(etype);
        Py_XDECREF(evalue);
        Py_XDECREF(etraceback);
    } else {
        Py_XINCREF(self->ll);
        if(!PyObject_TypeCheck(self->ll, state->LayerListType)) {
            PyErr_SetString(PyExc_TypeError, "first argument must be a LayerList");
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
                         &(self->ll), &py_surface, &tw, &th)) {
        PyErr_Fetch(&etype, &evalue, &etraceback);
        Py_XDECREF(etype);
        Py_XDECREF(evalue);
        Py_XDECREF(etraceback);
    } else {
        Py_XINCREF(self->ll);
        Py_XINCREF(py_surface);
        if(!PyObject_TypeCheck(self->ll, state->LayerListType)) {
            PyErr_SetString(PyExc_TypeError, "first argument must be a LayerList");
            goto error;
        }
        if(!PyObject_TypeCheck(py_surface, state->LP_SDL_Surface)) {
            PyErr_SetString(PyExc_TypeError, "second argument must be a SDL_Surface");
            goto error;
        }
        surface = (SDL_Surface *)get_value_from_lp_object(state, py_surface);
        if(surface == NULL) {
            PyErr_SetString(PyExc_RuntimeError, "couldn't get pointer of SDL_Surface");
            goto error;
        }

        self->tileset = tilemap_add_tileset(self->ll->ll, surface, tw, th);
        if(self->tileset < 0) {
            PyErr_SetString(state->CrustyException, "tilemap_add_tileset failed");
            goto error;
        }

        Py_DECREF(py_surface);
        return(0);
    }

    /* fell through, so just set a generic error that everything failed */
    PyErr_SetString(PyExc_TypeError, "invalid arguments for tileset creation");

error:
    Py_XDECREF(py_surface);
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

static PyObject *LayerList_TS_Tilemap(TilesetObject *self,
                                      PyTypeObject *defining_class,
                                      PyObject *const *args,
                                      Py_ssize_t nargs,
                                      PyObject *kwnames) {
    PyObject *arglist;
    PyObject *tilemap;

    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this LayerList is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 2) {
        PyErr_SetString(PyExc_TypeError, "this function needs 2 arguments");
        return(NULL);
    }

    arglist = PyTuple_Pack(4, self->ll, self, args[0], args[1]);
    if(arglist == NULL) {
        return(NULL);
    }
    tilemap = PyObject_CallObject(state->TilemapType, arglist);
    Py_DECREF(arglist);
    if(tilemap == NULL) {
        return(NULL);
    }

    return(tilemap);
}

static PyMethodDef Tileset_methods[] = {
    {
        "Tilemap",
        (PyCMethod) LayerList_TS_Tilemap,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Convenience method to create a Tilemap from this Tileset."},
    {NULL}
};

static PyType_Slot TilesetSlots[] = {
    {Py_tp_new, Tileset_new},
    {Py_tp_init, (initproc)Tileset_init},
    {Py_tp_dealloc, (destructor)Tileset_dealloc},
    {Py_tp_traverse, heap_type_traverse},
    {Py_tp_methods, Tileset_methods},
    {0, NULL}
};

static PyType_Spec TilesetSpec = {
    .name = "crustygame.Tileset",
    .basicsize = sizeof(TilesetObject),
    .itemsize = 0,
    .flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .slots = TilesetSlots
};

static PyObject *Tilemap_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {
    TilemapObject *self;

    self = (TilemapObject *)type->tp_alloc(type, 0);
    if(self == NULL) {
        return(NULL);
    }
    self->ll = NULL;
    self->ts = NULL;
    self->tilemap = -1;
 
    return((PyObject *)self);
}

static int Tilemap_init(TilemapObject *self, PyObject *args, PyObject *kwds) {
    unsigned int w, h;

    if(self->ll != NULL) {
        PyErr_SetString(PyExc_TypeError, "Tilemap already initialized");
        return(-1);
    }

    crustygame_state *state = PyType_GetModuleState(Py_TYPE(self));

    if(!PyArg_ParseTuple(args, "OOII", &(self->ll), &(self->ts), &w, &h)) {
        return(-1);
    }
    Py_XINCREF(self->ll);
    Py_XINCREF(self->ts);
    if(!PyObject_TypeCheck(self->ll, state->LayerListType)) {
        PyErr_SetString(PyExc_TypeError, "first argument must be a LayerList");
        goto error;
    }
    if(!PyObject_TypeCheck(self->ts, state->TilesetType)) {
        PyErr_SetString(PyExc_TypeError, "second argument must be a Tileset");
        goto error;
    }

    self->tilemap = tilemap_add_tilemap(self->ll->ll, self->ts->tileset, w, h);
    if(self->tilemap < 0) {
        PyErr_SetString(state->CrustyException, "tilemap_add_tilemap failed");
        goto error;
    }

    return(0);

error:
    Py_CLEAR(self->ts);
    Py_CLEAR(self->ll);
    return(-1);
}

static void Tilemap_dealloc(TilemapObject *self) {
    if(self->tilemap >= 0) {
        tilemap_free_tilemap(self->ll->ll, self->tilemap);
        Py_DECREF(self->ll);
    }
    Py_XDECREF(self->ts);
    Py_TYPE(self)->tp_free((PyObject *) self);
}

static PyObject *Tilemap_set_tileset(TilemapObject *self,
                                     PyTypeObject *defining_class,
                                     PyObject *const *args,
                                     Py_ssize_t nargs,
                                     PyObject *kwnames) {
    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Tilemap is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    if(!PyObject_TypeCheck(args[0], state->TilesetType)) {
        PyErr_SetString(PyExc_TypeError, "tileset must be a Tileset.");
        return(NULL);
    }
    TilesetObject *newts = (TilesetObject *)args[0];
    Py_CLEAR(self->ts);

    if(tilemap_set_tilemap_tileset(self->ll->ll,
                                   self->tilemap,
                                   newts->tileset) < 0) {
        PyErr_SetString(state->CrustyException, "Couldn't set tileset.");
        return(NULL);
    }
    self->ts = newts;
    Py_INCREF(newts);

    Py_RETURN_NONE;
}

static PyObject *Tilemap_set_map(TilemapObject *self,
                                 PyTypeObject *defining_class,
                                 PyObject *const *args,
                                 Py_ssize_t nargs,
                                 PyObject *kwnames) {
    unsigned long x, y;
    long pitch, w, h;
    Py_buffer buf;

    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Tilemap is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 6) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 6 argument");
        return(NULL);
    }
    x = PyLong_AsUnsignedLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
    y = PyLong_AsUnsignedLong(args[1]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
    pitch = PyLong_AsLong(args[2]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
    w = PyLong_AsLong(args[3]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
    h = PyLong_AsLong(args[4]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
    if(PyObject_GetBuffer(args[5], &buf, PyBUF_CONTIG_RO) < 0) {
        return(NULL);
    }

    /* buf and len are in terms of char *, but tilemap methods are in terms of
     * ints */
    if(tilemap_set_tilemap_map(self->ll->ll,
                               self->tilemap,
                               x, y, pitch, w, h,
                               (unsigned int *)(buf.buf),
                               buf.len / sizeof(unsigned int)) < 0) {
        PyErr_SetString(state->CrustyException, "tilemap_set_tilemap_map failed");
        PyBuffer_Release(&buf);
        return(NULL);
    }

    PyBuffer_Release(&buf);
    Py_RETURN_NONE;
}

static PyObject *Tilemap_set_attr_flags(TilemapObject *self,
                                        PyTypeObject *defining_class,
                                        PyObject *const *args,
                                        Py_ssize_t nargs,
                                        PyObject *kwnames) {
    unsigned long x, y;
    long pitch, w, h;
    Py_buffer buf;

    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Tilemap is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 6) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 6 argument");
        return(NULL);
    }
    x = PyLong_AsUnsignedLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
    y = PyLong_AsUnsignedLong(args[1]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
    pitch = PyLong_AsLong(args[2]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
    w = PyLong_AsLong(args[3]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
    h = PyLong_AsLong(args[4]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
    if(PyObject_GetBuffer(args[5], &buf, PyBUF_CONTIG_RO) < 0) {
        return(NULL);
    }
    
    if(tilemap_set_tilemap_attr_flags(self->ll->ll,
                                      self->tilemap,
                                      x, y, pitch, w, h,
                                      (unsigned int *)(buf.buf),
                                      buf.len / sizeof(unsigned int)) < 0) {
        PyErr_SetString(state->CrustyException, "tilemap_set_tilemap_attr_flags failed");
        PyBuffer_Release(&buf);
        return(NULL);
    }

    PyBuffer_Release(&buf);
    Py_RETURN_NONE;
}

static PyObject *Tilemap_set_attr_colormod(TilemapObject *self,
                                           PyTypeObject *defining_class,
                                           PyObject *const *args,
                                           Py_ssize_t nargs,
                                           PyObject *kwnames) {
    unsigned long x, y;
    long pitch, w, h;
    Py_buffer buf;

    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Tilemap is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 6) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 6 argument");
        return(NULL);
    }
    x = PyLong_AsUnsignedLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
    y = PyLong_AsUnsignedLong(args[1]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
    pitch = PyLong_AsLong(args[2]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
    w = PyLong_AsLong(args[3]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
    h = PyLong_AsLong(args[4]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
    if(PyObject_GetBuffer(args[5], &buf, PyBUF_CONTIG_RO) < 0) {
        return(NULL);
    }
    
    if(tilemap_set_tilemap_attr_colormod(self->ll->ll,
                                         self->tilemap,
                                         x, y, pitch, w, h,
                                         (unsigned int *)(buf.buf),
                                         buf.len / sizeof(unsigned int)) < 0) {
        PyErr_SetString(state->CrustyException, "tilemap_set_tilemap_attr_colormod failed");
        PyBuffer_Release(&buf);
        return(NULL);
    }

    PyBuffer_Release(&buf);
    Py_RETURN_NONE;
}

static PyObject *Tilemap_update(TilemapObject *self,
                                PyTypeObject *defining_class,
                                PyObject *const *args,
                                Py_ssize_t nargs,
                                PyObject *kwnames) {
    unsigned long x, y, w, h;

    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Tilemap is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 4) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 4 argument");
        return(NULL);
    }
    x = PyLong_AsUnsignedLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
    y = PyLong_AsUnsignedLong(args[1]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
    w = PyLong_AsUnsignedLong(args[2]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
    h = PyLong_AsUnsignedLong(args[3]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
    
    if(tilemap_update_tilemap(self->ll->ll, self->tilemap, x, y, w, h) < 0) {
        PyErr_SetString(state->CrustyException, "tilemap_update_tilemap failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *LayerList_TM_Layer(TilemapObject *self,
                                    PyTypeObject *defining_class,
                                    PyObject *const *args,
                                    Py_ssize_t nargs,
                                    PyObject *kwnames) {
    PyObject *arglist;
    PyObject *layer;

    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this LayerList is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    arglist = PyTuple_Pack(2, self->ll, self);
    if(arglist == NULL) {
        return(NULL);
    }
    layer = PyObject_CallObject(state->LayerType, arglist);
    Py_DECREF(arglist);
    if(layer == NULL) {
        return(NULL);
    }

    return(layer);
}

static PyMethodDef Tilemap_methods[] = {
    {
        "tileset",
        (PyCMethod) Tilemap_set_tileset,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set a tileset which will be used for rendering out the tilemap."},
    {
        "map",
        (PyCMethod) Tilemap_set_map,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Update a rectangle section of the tilemap."},
    {
        "attr_flags",
        (PyCMethod) Tilemap_set_attr_flags,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Add/update attribute flags to a tilemap."},
    {
        "attr_colormod",
        (PyCMethod) Tilemap_set_attr_colormod,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Add/update colormod values for a tilemap."},
    {
        "update",
        (PyCMethod) Tilemap_update,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Redraw a region of the tilemap."},
    {
        "Layer",
        (PyCMethod) LayerList_TM_Layer,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Convenience method to create a Layer from this Tilemap."},
    {NULL}
};

static PyType_Slot TilemapSlots[] = {
    {Py_tp_new, Tilemap_new},
    {Py_tp_init, (initproc)Tilemap_init},
    {Py_tp_dealloc, (destructor)Tilemap_dealloc},
    {Py_tp_traverse, heap_type_traverse},
    {Py_tp_methods, Tilemap_methods},
    {0, NULL}
};

static PyType_Spec TilemapSpec = {
    .name = "crustygame.Tilemap",
    .basicsize = sizeof(TilemapObject),
    .itemsize = 0,
    .flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .slots = TilemapSlots
};

static PyObject *Layer_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {
    LayerObject *self;

    self = (LayerObject *)type->tp_alloc(type, 0);
    if(self == NULL) {
        return(NULL);
    }
    self->ll = NULL;
    self->tm = NULL;
    self->layer = -1;
 
    return((PyObject *)self);
}

static int Layer_init(LayerObject *self, PyObject *args, PyObject *kwds) {
    if(self->ll != NULL) {
        PyErr_SetString(PyExc_TypeError, "Layer already initialized");
        return(-1);
    }

    crustygame_state *state = PyType_GetModuleState(Py_TYPE(self));

    if(!PyArg_ParseTuple(args, "OO", &(self->ll), &(self->tm))) {
        return(-1);
    }
    Py_XINCREF(self->ll);
    Py_XINCREF(self->tm);
    if(!PyObject_TypeCheck(self->ll, state->LayerListType)) {
        PyErr_SetString(PyExc_TypeError, "first argument must be a LayerList");
        goto error;
    }
    if(!PyObject_TypeCheck(self->tm, state->TilemapType)) {
        PyErr_SetString(PyExc_TypeError, "second argument must be a Tilemap");
        goto error;
    }

    self->layer = tilemap_add_layer(self->ll->ll, self->tm->tilemap);
    if(self->layer < 0) {
        PyErr_SetString(state->CrustyException, "tilemap_add_layer failed");
        goto error;
    }

    return(0);

error:
    Py_CLEAR(self->tm);
    Py_CLEAR(self->ll);
    return(-1);
}

static void Layer_dealloc(LayerObject *self) {
    if(self->layer >= 0) {
        tilemap_free_layer(self->ll->ll, self->layer);
        Py_DECREF(self->ll);
    }
    Py_XDECREF(self->tm);
    Py_TYPE(self)->tp_free((PyObject *) self);
}

static PyObject *Tilemap_set_layer_pos(LayerObject *self,
                                       PyTypeObject *defining_class,
                                       PyObject *const *args,
                                       Py_ssize_t nargs,
                                       PyObject *kwnames) {
    long x, y;

    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Layer is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 2) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 2 argument");
        return(NULL);
    }
    x = PyLong_AsLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
    y = PyLong_AsLong(args[1]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
   
    if(tilemap_set_layer_pos(self->ll->ll, self->layer, x, y) < 0) {
        PyErr_SetString(state->CrustyException, "tilemap_set_layer_pos failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Tilemap_set_layer_window(LayerObject *self,
                                          PyTypeObject *defining_class,
                                          PyObject *const *args,
                                          Py_ssize_t nargs,
                                          PyObject *kwnames) {
    unsigned long w, h;

    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Layer is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 2) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 2 argument");
        return(NULL);
    }
    w = PyLong_AsUnsignedLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
    h = PyLong_AsUnsignedLong(args[1]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
   
    if(tilemap_set_layer_window(self->ll->ll, self->layer, w, h) < 0) {
        PyErr_SetString(state->CrustyException, "tilemap_set_layer_window failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Tilemap_set_layer_scroll_pos(LayerObject *self,
                                              PyTypeObject *defining_class,
                                              PyObject *const *args,
                                              Py_ssize_t nargs,
                                              PyObject *kwnames) {
    unsigned long x, y;

    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Layer is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 2) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 2 argument");
        return(NULL);
    }
    x = PyLong_AsUnsignedLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
    y = PyLong_AsUnsignedLong(args[1]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
   
    if(tilemap_set_layer_scroll_pos(self->ll->ll, self->layer, x, y) < 0) {
        PyErr_SetString(state->CrustyException, "tilemap_set_layer_scroll_pos failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Tilemap_set_layer_scale(LayerObject *self,
                                         PyTypeObject *defining_class,
                                         PyObject *const *args,
                                         Py_ssize_t nargs,
                                         PyObject *kwnames) {
    double x, y;

    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Layer is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 2) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 2 argument");
        return(NULL);
    }
    x = PyFloat_AsDouble(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
    y = PyFloat_AsDouble(args[1]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
   
    if(tilemap_set_layer_scale(self->ll->ll, self->layer, x, y) < 0) {
        PyErr_SetString(state->CrustyException, "tilemap_set_layer_scale failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Tilemap_set_layer_rotation_center(LayerObject *self,
                                                   PyTypeObject *defining_class,
                                                   PyObject *const *args,
                                                   Py_ssize_t nargs,
                                                   PyObject *kwnames) {
    long x, y;

    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Layer is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 2) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 2 argument");
        return(NULL);
    }
    x = PyLong_AsLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
    y = PyLong_AsLong(args[1]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
   
    if(tilemap_set_layer_rotation_center(self->ll->ll, self->layer, x, y) < 0) {
        PyErr_SetString(state->CrustyException, "tilemap_set_layer_rotation_center failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Tilemap_set_layer_rotation(LayerObject *self,
                                            PyTypeObject *defining_class,
                                            PyObject *const *args,
                                            Py_ssize_t nargs,
                                            PyObject *kwnames) {
    double rot;

    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Layer is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 2 argument");
        return(NULL);
    }
    rot = PyFloat_AsDouble(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
  
    if(tilemap_set_layer_rotation(self->ll->ll, self->layer, rot) < 0) {
        PyErr_SetString(state->CrustyException, "tilemap_set_layer_rotation failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Tilemap_set_layer_colormod(LayerObject *self,
                                            PyTypeObject *defining_class,
                                            PyObject *const *args,
                                            Py_ssize_t nargs,
                                            PyObject *kwnames) {
    unsigned long colormod;

    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Layer is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 2 argument");
        return(NULL);
    }
    colormod = PyLong_AsUnsignedLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
   
    if(tilemap_set_layer_colormod(self->ll->ll, self->layer, colormod) < 0) {
        PyErr_SetString(state->CrustyException, "tilemap_set_layer_colormod failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Tilemap_set_layer_blendmode(LayerObject *self,
                                             PyTypeObject *defining_class,
                                             PyObject *const *args,
                                             Py_ssize_t nargs,
                                             PyObject *kwnames) {
    long blendmode;

    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Layer is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 2 argument");
        return(NULL);
    }
    blendmode = PyLong_AsLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
   
    if(tilemap_set_layer_blendmode(self->ll->ll, self->layer, blendmode) < 0) {
        PyErr_SetString(state->CrustyException, "tilemap_set_layer_blendmode failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Tilemap_draw_layer(LayerObject *self,
                                    PyTypeObject *defining_class,
                                    PyObject *const *args,
                                    Py_ssize_t nargs,
                                    PyObject *kwnames) {
    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Layer is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(tilemap_draw_layer(self->ll->ll, self->layer) < 0) {
        PyErr_SetString(state->CrustyException, "tilemap_draw_layer failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyMethodDef Layer_methods[] = {
    {
        "pos",
        (PyCMethod) Tilemap_set_layer_pos,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the on-screen position to draw the layer to."},
    {
        "window",
        (PyCMethod) Tilemap_set_layer_window,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the window size of the view in to the tilemap to show."},
    {
        "scroll_pos",
        (PyCMethod) Tilemap_set_layer_scroll_pos,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the scroll position (top-left corner) of the tilemap to show."},
    {
        "scale",
        (PyCMethod) Tilemap_set_layer_scale,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the scale of the layer."},
    {
        "rotation_center",
        (PyCMethod) Tilemap_set_layer_rotation_center,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the point around which the layer is rotated."},
    {
        "rotation",
        (PyCMethod) Tilemap_set_layer_rotation,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the rotation of the layer, in degrees."},
    {
        "colormod",
        (PyCMethod) Tilemap_set_layer_colormod,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the layer's colormod."},
    {
        "blendmode",
        (PyCMethod) Tilemap_set_layer_blendmode,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the layer blendmode."},
    {
        "draw",
        (PyCMethod) Tilemap_draw_layer,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Finally, draw a layer to the screen or render target."},
    {NULL}
};

static PyType_Slot LayerSlots[] = {
    {Py_tp_new, Layer_new},
    {Py_tp_init, (initproc)Layer_init},
    {Py_tp_dealloc, (destructor)Layer_dealloc},
    {Py_tp_traverse, heap_type_traverse},
    {Py_tp_methods, Layer_methods},
    {0, NULL}
};

static PyType_Spec LayerSpec = {
    .name = "crustygame.Layer",
    .basicsize = sizeof(LayerObject),
    .itemsize = 0,
    .flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .slots = LayerSlots
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
    state->TilesetType = NULL;
    state->TilemapType = NULL;
    state->LayerType = NULL;
    state->return_ptr = NULL;
    state->LP_SDL_Renderer = NULL;
    state->LP_SDL_Texture = NULL;
    state->LP_SDL_Surface = NULL;
    PyObject *ctypes_m = NULL;
    PyObject *ctypes_POINTER = NULL;
    PyObject *ctypes_CDLL = NULL;
    PyObject *ctypes_ulong = NULL;
    PyObject *ctypes_void_p = NULL;
    PyObject *filename = NULL;
    PyObject *ctypes_this_module = NULL;
    PyObject *argtypes_tuple = NULL;
    PyObject *SDL_m = NULL;

    /* import sdl2 to get the literal pointer types needed for type checks. */
    /* This has to happen early otherwise weirdness happens that I don't
     * understand and stuff crashes. */
    SDL_m = PyImport_ImportModule("sdl2");
    if(SDL_m == NULL) {
        goto error;
    }

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
    state->TilemapType = (PyTypeObject *)PyType_FromModuleAndSpec(m, &TilemapSpec, NULL);
    if(PyModule_AddObject(m, "Tilemap", (PyObject *)state->TilemapType) < 0) {
        goto error;
    }
    state->LayerType = (PyTypeObject *)PyType_FromModuleAndSpec(m, &LayerSpec, NULL);
    if(PyModule_AddObject(m, "Layer", (PyObject *)state->LayerType) < 0) {
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
    /* do some awful hackery so pointer values can be extracted directly from
     * ctypes LP_* types.  Use a method that returns an intptr_t when passed
     * a ctypes LP_* type by importing this module with ctypes, grabbing that
     * method as a ctypes callable and setting the right attributes on it. */
    ctypes_CDLL = get_symbol_from_string(ctypes_m, "CDLL");
    Py_XINCREF(ctypes_CDLL);
    if(ctypes_CDLL == NULL) {
        goto error;
    }
    /* types that'll be needed */
    ctypes_ulong = get_symbol_from_string(ctypes_m, "c_ulong");
    Py_XINCREF(ctypes_ulong);
    if(ctypes_ulong == NULL) {
        goto error;
    }
    ctypes_void_p = get_symbol_from_string(ctypes_m, "c_void_p");
    Py_XINCREF(ctypes_void_p);
    if(ctypes_void_p == NULL) {
        goto error;
    }
    /* get this filename to import this module */
    filename = PyModule_GetFilenameObject(m);
    if(filename == NULL) {
        goto error;
    }
    /* import it */
    ctypes_this_module = PyObject_CallOneArg(ctypes_CDLL, filename);
    if(ctypes_this_module == NULL) {
        goto error;
    }
    /* get the adapter function */
    state->return_ptr = PyObject_GetAttrString(ctypes_this_module,
                                               "awful_return_ptr_hack_funct");
    Py_XINCREF(state->return_ptr);
    if(state->return_ptr == NULL) {
        goto error;
    }
    /* set its return type to be 64 bits... might want to do some extra stuff
     * to assure 32 bit platform support */
    if(PyObject_SetAttrString(state->return_ptr, "restype", ctypes_ulong) < 0) {
        goto error;
    }
    /* put the pointer argument type in a tuple because that's how it has to be
     * then pass it in as the argument type. */
    argtypes_tuple = PyTuple_Pack(1, ctypes_void_p);
    if(argtypes_tuple == NULL) {
        goto error;
    }
    if(PyObject_SetAttrString(state->return_ptr, "argtypes", argtypes_tuple) < 0) {
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

    if(PyModule_AddIntMacro(m, TILEMAP_HFLIP_MASK) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, TILEMAP_VFLIP_MASK) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, TILEMAP_ROTATE_MASK) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, TILEMAP_ROTATE_NONE) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, TILEMAP_ROTATE_90) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, TILEMAP_ROTATE_180) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, TILEMAP_ROTATE_270) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, TILEMAP_BLENDMODE_BLEND) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, TILEMAP_BLENDMODE_ADD) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, TILEMAP_BLENDMODE_MOD) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, TILEMAP_BLENDMODE_MUL) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, TILEMAP_BLENDMODE_SUB) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, TILEMAP_BSHIFT) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, TILEMAP_BMASK) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, TILEMAP_GSHIFT) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, TILEMAP_GMASK) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, TILEMAP_RSHIFT) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, TILEMAP_RMASK) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, TILEMAP_ASHIFT) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, TILEMAP_AMASK) < 0) {
        goto error;
    }

    Py_DECREF(SDL_m);
    Py_DECREF(argtypes_tuple);
    Py_DECREF(ctypes_this_module);
    Py_DECREF(filename);
    Py_DECREF(ctypes_void_p);
    Py_DECREF(ctypes_ulong);
    Py_DECREF(ctypes_CDLL);
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
    Py_CLEAR(state->return_ptr);
    Py_XDECREF(argtypes_tuple);
    Py_XDECREF(ctypes_this_module);
    Py_XDECREF(filename);
    Py_XDECREF(ctypes_void_p);
    Py_XDECREF(ctypes_ulong);
    Py_XDECREF(ctypes_CDLL);
    Py_XDECREF(ctypes_POINTER);
    Py_XDECREF(ctypes_m);
    Py_CLEAR(state->LayerType);
    Py_CLEAR(state->TilemapType);
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
    Py_XDECREF(state->return_ptr);
    Py_XDECREF(state->LayerType);
    Py_XDECREF(state->TilemapType);
    Py_XDECREF(state->TilesetType);
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
