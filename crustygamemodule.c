#include <stdint.h>

#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "tilemap.h"
#include "synth.h"

typedef struct {
    PyObject *CrustyException;
    PyTypeObject *LayerListType;
    PyTypeObject *TilesetType;
    PyTypeObject *TilemapType;
    PyTypeObject *LayerType;
    PyTypeObject *SynthType;
    PyTypeObject *BufferType;
    PyTypeObject *InternalBufferType;
    PyTypeObject *PlayerType;
    PyTypeObject *FilterType;

    /* ctypes callable which will point to the function a bit further down */
    PyObject *return_ptr;

    /* types needed type type checking */
    PyTypeObject *LP_SDL_Renderer;
    PyTypeObject *LP_SDL_Texture;
    PyTypeObject *LP_SDL_Surface;
} crustygame_state;

typedef struct {
    PyObject *cb;
    PyObject *priv;
} CrustyCallback;

typedef struct {
    PyObject_HEAD
    LayerList *ll;
    CrustyCallback log;
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

typedef struct LayerObject_s {
    PyObject_HEAD
    LayerListObject *ll;
    TilemapObject *tm;
    PyObject *tex;
    struct LayerObject_s *relative;
    int layer;
} LayerObject;

typedef struct BufferObject_s BufferObject;

typedef struct {
    PyObject_HEAD
    Synth *s;
    CrustyCallback synth_frame;
    CrustyCallback log;
    int channels;
    BufferObject **outputBuffers;
} SynthObject;

typedef struct BufferObject_s {
    PyObject_HEAD
    SynthObject *s;
    int buffer;
    unsigned int rate;
} BufferObject;

typedef struct InternalBufferObject_s {
    PyObject_HEAD
    SynthObject *s;
    BufferObject *b;
    float *data;
    int size;
} InternalBufferObject;

typedef struct {
    PyObject_HEAD
    SynthObject *s;
    BufferObject *inBuffer;
    BufferObject *outBuffer;
    BufferObject *volBuffer;
    BufferObject *startBuffer;
    BufferObject *lengthBuffer;
    BufferObject *phaseBuffer;
    BufferObject *speedBuffer;
    int player;
} PlayerObject;

typedef struct {
    PyObject_HEAD
    SynthObject *s;
    BufferObject *inBuffer;
    BufferObject *filterBuffer;
    BufferObject *sliceBuffer;
    BufferObject *outBuffer;
    BufferObject *volBuffer;
    int filter;
} FilterObject;

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
static void log_cb_adapter(CrustyCallback *cb, const char *str) {
    PyObject *arglist;
    PyObject *result;

    arglist = Py_BuildValue("Os", cb->priv, str);
    result = PyObject_CallObject(cb->cb, arglist);
    Py_DECREF(arglist);
    /* don't check the result because this is called by C code anyway and it
     * is void */
    Py_XDECREF(result);
}

static int synth_cb_adapter(CrustyCallback *cb, Synth *s) {
    PyObject *arglist;
    PyObject *result;
    int ret;

    arglist = Py_BuildValue("(O)", cb->priv);
    result = PyObject_CallObject(cb->cb, arglist);
    Py_DECREF(arglist);
    ret = PyLong_AsLong(result);
    Py_DECREF(result);

    return(ret);
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
    self->py_renderer = NULL;
    self->log.cb = NULL;
    self->log.priv = NULL;

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
                         &(self->py_renderer),
                         &format,
                         &(self->log.cb),
                         &(self->log.priv))) {
        self->py_renderer = NULL;
        self->log.cb = NULL;
        self->log.priv = NULL;
        return(-1);
    }
    Py_XINCREF(self->py_renderer);
    Py_XINCREF(self->log.cb);
    Py_XINCREF(self->log.priv);

    if(!PyObject_TypeCheck(self->py_renderer, state->LP_SDL_Renderer)) {
        PyErr_SetString(PyExc_TypeError, "got something not an SDL_Renderer");
        goto error;
    }
    if(!PyCallable_Check(self->log.cb)) {
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
                             &(self->log));
    if(self->ll == NULL) {
        PyErr_SetString(state->CrustyException, "layerlist_new returned an error");
        goto error;
    }

    return(0);

error:
    Py_CLEAR(self->log.priv);
    Py_CLEAR(self->log.cb);
    Py_CLEAR(self->py_renderer);
    return(-1);
}

static void LayerList_dealloc(LayerListObject *self) {
    if(self->ll != NULL) {
        layerlist_free(self->ll);
    }
    Py_XDECREF(self->log.priv);
    Py_XDECREF(self->log.cb);
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

    if(nargs == 4) {
        arglist = PyTuple_Pack(5, self, args[0], args[1], args[2], args[3]);
    } else if(nargs == 6) {
        arglist = PyTuple_Pack(7, self, args[0], args[1], args[2], args[3], args[4], args[5]);
    } else {
        PyErr_SetString(PyExc_TypeError, "this function needs 4 or 6 arguments");
        return(NULL);
    }

    if(arglist == NULL) {
        return(NULL);
    }
    tileset = PyObject_CallObject((PyObject *)(state->TilesetType), arglist);
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

    if(nargs < 4) {
        PyErr_SetString(PyExc_TypeError, "this function needs 4 arguments");
        return(NULL);
    }

    arglist = PyTuple_Pack(5, self, args[0], args[1], args[2], args[3]);
    if(arglist == NULL) {
        return(NULL);
    }
    tilemap = PyObject_CallObject((PyObject *)(state->TilemapType), arglist);
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
        "Set the default texture to render to.  Isn't applied immediately, though.\n\n"
        "default_render_target(texture)\n"
        "texture  An SDL_Texture or None for the screen"},
    {
        "target_tileset",
        (PyCMethod) LayerList_set_target_tileset,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the tileset to render to or the default render target if less than 0.\n\n"
        "target_tileset(tileset)\n"
        "tileset  A Tileset or None to output to the default render target"},
    {
        "tileset",
        (PyCMethod) LayerList_LL_Tileset,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Convenience method to create a Tileset from this LayerList.\n\n"
        "tileset(...) -> tileset\n"
        "...  See Tileset constructor, without layerlist argument"},
    {
        "tilemap",
        (PyCMethod) LayerList_LL_Tilemap,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Convenience method to create a Tilemap from this LayerList.\n\n"
        "tilemap(...) -> tileset\n"
        "...  See Tilemap constructor, without layerlist argument"},
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
    {"renderer", (getter) LayerList_getrenderer, NULL, "Get the renderer back from the LayerList.", NULL},
    {NULL}
};

/* Needed for heap-based type instantiation.  Hopefully future proof for this
 * project.  Its benefits seem worth the bit of extra complexity. */
static PyType_Slot LayerListSlots[] = {
    {Py_tp_doc, "The base LayerList context.  Function arguments are generally documented here\n"
                "but for detailed documentation, see the HTML docs.\n\n"
                "LayerList(renderer, format, log_cb, log_priv)\n"
                "renderer  An SDL_Renderer.\n"
                "format    An integer SDL pixel format.\n"
                "log_cb    A method to be called when the LayerList emits logging output:\n"
                "              log_cb(log_priv, message)\n"
                "log_priv  An object that will be passed to log_cb."},
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
    PyObject *name = NULL;
    const char *cname;
    PyObject *etype, *evalue, *etraceback;

    if(self->ll != NULL) {
        PyErr_SetString(PyExc_TypeError, "Tileset already initialized");
        return(-1);
    }

    crustygame_state *state = PyType_GetModuleState(Py_TYPE(self));

    /* first try to see if a blank tileset is requested, as it has the most
     * number of arguments and would definitely fail if the wrong amount of
     * arguments was provided */
    if(!PyArg_ParseTuple(args, "OIIIIIO",
                         &(self->ll), &w, &h, &color, &tw, &th, &name)) {
        self->ll = NULL;
        PyErr_Fetch(&etype, &evalue, &etraceback);
        /* don't care too much to inspect what went wrong, just try something
         * else anyway */
        Py_XDECREF(etype);
        Py_XDECREF(evalue);
        Py_XDECREF(etraceback);
    } else {
        Py_XINCREF(self->ll);
        Py_XINCREF(name);
        if(!PyObject_TypeCheck(self->ll, state->LayerListType)) {
            PyErr_SetString(PyExc_TypeError, "first argument must be a LayerList");
            goto error;
        }

        if(name == Py_None) {
            cname = NULL;
        } else {
            cname = PyUnicode_AsUTF8(name);
            if(cname == NULL) {
                goto error;
            }
        }

        self->tileset = tilemap_blank_tileset(self->ll->ll, w, h, color, tw, th, cname);
        Py_CLEAR(name);
        if(self->tileset < 0) {
            PyErr_SetString(state->CrustyException, "tilemap_blank_tileset failed");
            goto error;
        }

        return(0);
    }

    /* now check if a string is provided, and if so use it as a filename */
    if(!PyArg_ParseTuple(args, "OsIIO",
                         &(self->ll), &filename, &tw, &th, &name)) {
        self->ll = NULL;
        PyErr_Fetch(&etype, &evalue, &etraceback);
        Py_XDECREF(etype);
        Py_XDECREF(evalue);
        Py_XDECREF(etraceback);
    } else {
        Py_XINCREF(self->ll);
        Py_XINCREF(name);
        if(!PyObject_TypeCheck(self->ll, state->LayerListType)) {
            PyErr_SetString(PyExc_TypeError, "first argument must be a LayerList");
            goto error;
        }

        if(name == Py_None) {
            cname = NULL;
        } else {
            cname = PyUnicode_AsUTF8(name);
            if(cname == NULL) {
                goto error;
            }
        }

        self->tileset = tilemap_tileset_from_bmp(self->ll->ll,
                                                 filename,
                                                 tw, th,
                                                 cname);
        Py_CLEAR(name);
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
    if(!PyArg_ParseTuple(args, "OOIIO",
                         &(self->ll), &py_surface, &tw, &th, &name)) {
        self->ll = NULL;
        PyErr_Fetch(&etype, &evalue, &etraceback);
        Py_XDECREF(etype);
        Py_XDECREF(evalue);
        Py_XDECREF(etraceback);
    } else {
        Py_XINCREF(self->ll);
        Py_XINCREF(py_surface);
        Py_XINCREF(name);
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

        if(name == Py_None) {
            cname = NULL;
        } else {
            cname = PyUnicode_AsUTF8(name);
            if(cname == NULL) {
                goto error;
            }
        }

        self->tileset = tilemap_add_tileset(self->ll->ll, surface, tw, th, cname);
        Py_CLEAR(name);
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
    Py_XDECREF(name);
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

static PyObject *Tilemap_tileset_name(TilesetObject *self,
                                      PyTypeObject *defining_class,
                                      PyObject *const *args,
                                      Py_ssize_t nargs,
                                      PyObject *kwnames) {
    const char *name;

    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Tileset is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    name = tilemap_tileset_name(self->ll->ll, self->tileset);
    if(name == NULL) {
        PyErr_SetString(state->CrustyException, "tilemap_tileset_name failed");
        return(NULL);
    }

    return(PyUnicode_FromString(name));
}

static PyObject *Tilemap_tileset_tiles(TilesetObject *self,
                                       PyTypeObject *defining_class,
                                       PyObject *const *args,
                                       Py_ssize_t nargs,
                                       PyObject *kwnames) {
    int ret;

    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Tileset is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    ret = tilemap_tileset_tiles(self->ll->ll, self->tileset);
    if(ret < 0) {
        PyErr_SetString(state->CrustyException, "tilemap_tileset_tiles failed");
        return(NULL);
    }

    return(PyLong_FromLong(ret));
}

static PyObject *Tilemap_tileset_tile_width(TilesetObject *self,
                                            PyTypeObject *defining_class,
                                            PyObject *const *args,
                                            Py_ssize_t nargs,
                                            PyObject *kwnames) {
    int ret;

    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Tileset is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    ret = tilemap_tileset_tile_width(self->ll->ll, self->tileset);
    if(ret < 0) {
        PyErr_SetString(state->CrustyException, "tilemap_tileset_tile_width failed");
        return(NULL);
    }

    return(PyLong_FromLong(ret));
}

static PyObject *Tilemap_tileset_tile_height(TilesetObject *self,
                                             PyTypeObject *defining_class,
                                             PyObject *const *args,
                                             Py_ssize_t nargs,
                                             PyObject *kwnames) {
    int ret;

    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Tileset is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    ret = tilemap_tileset_tile_height(self->ll->ll, self->tileset);
    if(ret < 0) {
        PyErr_SetString(state->CrustyException, "tilemap_tileset_tile_height failed");
        return(NULL);
    }

    return(PyLong_FromLong(ret));
}

static PyObject *LayerList_TS_tilemap(TilesetObject *self,
                                      PyTypeObject *defining_class,
                                      PyObject *const *args,
                                      Py_ssize_t nargs,
                                      PyObject *kwnames) {
    PyObject *arglist;
    PyObject *tilemap;

    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Tileset is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 3) {
        PyErr_SetString(PyExc_TypeError, "this function needs 3 arguments");
        return(NULL);
    }

    arglist = PyTuple_Pack(5, self->ll, self, args[0], args[1], args[2]);
    if(arglist == NULL) {
        return(NULL);
    }
    tilemap = PyObject_CallObject((PyObject *)(state->TilemapType), arglist);
    Py_DECREF(arglist);
    if(tilemap == NULL) {
        return(NULL);
    }

    return(tilemap);
}

static PyMethodDef Tileset_methods[] = {
    {
        "name",
        (PyCMethod) Tilemap_tileset_name,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Get the tileset name.\n\n"
        "name() -> name\n"
        "name  The tileset's name."},
    {
        "tiles",
        (PyCMethod) Tilemap_tileset_tiles,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Get the number of tiles.\n\n"
        "tiles() -> tiles\n"
        "tiles  The number of tiles."},
    {
        "width",
        (PyCMethod) Tilemap_tileset_tile_width,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Get the width of a tile\n\n"
        "width() -> width\n"
        "width  The width of a tile."},
    {
        "height",
        (PyCMethod) Tilemap_tileset_tile_height,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Get the height of a tile.\n\n"
        "height() -> height\n"
        "height  The height of a tile."},
    {
        "tilemap",
        (PyCMethod) LayerList_TS_tilemap,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Convenience method to create a Tilemap from this Tileset.\n\n"
        "tilemap(...) -> tilemap\n"
        "...  See Tilemap constructor, without layerlist or tileset arguments"},
    {NULL}
};

static PyType_Slot TilesetSlots[] = {
    {Py_tp_doc, "A Tileset.\n\n"
                "Tileset(layerlist, width, height, fillcolor, tilewidth, tileheight, name)\n"
                "layerlist   A LayerList\n"
                "width       Width of the tileset\n"
                "height      Height of the tileset\n"
                "fillcolor   Fill color given from SDL_MapRGB and friends\n"
                "tilewidth   Width of each tile\n"
                "tileheight  Height of each tile\n"
                "name        Optional name or None\n\n"
                "Tileset(layerlist, bmpfilename, tilewidth, tileheight, name)\n"
                "layerlist    A LayerList\n"
                "bmpfilename  A path to a BMP file to load.\n"
                "tilewidth    Width of each tile\n"
                "tileheight   Height of each tile\n"
                "name         Optional name or None\n\n"
                "Tileset(layerlist, surface, tilewidth, tileheight, name\n"
                "layerlist   A LayerList\n"
                "surface     An SDL_Surface to copy from\n"
                "tilewidth   Width of each tile\n"
                "tileheight  Height of each tile\n"
                "name        Optional name or None"},
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
    PyObject *name = NULL;
    const char *cname;

    if(self->ll != NULL) {
        PyErr_SetString(PyExc_TypeError, "Tilemap already initialized");
        return(-1);
    }

    crustygame_state *state = PyType_GetModuleState(Py_TYPE(self));

    if(!PyArg_ParseTuple(args, "OOIIO", &(self->ll), &(self->ts), &w, &h, &name)) {
        self->ll = NULL;
        self->ts = NULL;
        return(-1);
    }
    Py_XINCREF(self->ll);
    Py_XINCREF(self->ts);
    Py_XINCREF(name);
    if(!PyObject_TypeCheck(self->ll, state->LayerListType)) {
        PyErr_SetString(PyExc_TypeError, "first argument must be a LayerList");
        goto error;
    }
    if(!PyObject_TypeCheck(self->ts, state->TilesetType)) {
        PyErr_SetString(PyExc_TypeError, "second argument must be a Tileset");
        goto error;
    }

    if(name == Py_None) {
        cname = NULL;
    } else {
        cname = PyUnicode_AsUTF8(name);
        if(cname == NULL) {
            goto error;
        }
    }

    self->tilemap = tilemap_add_tilemap(self->ll->ll, self->ts->tileset, w, h, cname);
    Py_CLEAR(name);
    if(self->tilemap < 0) {
        PyErr_SetString(state->CrustyException, "tilemap_add_tilemap failed");
        goto error;
    }

    return(0);

error:
    Py_XDECREF(name);
    Py_CLEAR(self->ts);
    Py_CLEAR(self->ll);
    return(-1);
}

static void Tilemap_dealloc(TilemapObject *self) {
    if(self->tilemap >= 0) {
        tilemap_free_tilemap(self->ll->ll, self->tilemap);
    }
    Py_XDECREF(self->ts);
    Py_XDECREF(self->ll);
    Py_TYPE(self)->tp_free((PyObject *) self);
}

static PyObject *Tilemap_tilemap_name(TilemapObject *self,
                                      PyTypeObject *defining_class,
                                      PyObject *const *args,
                                      Py_ssize_t nargs,
                                      PyObject *kwnames) {
    const char *name;

    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Tilemap is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    name = tilemap_tilemap_name(self->ll->ll, self->tilemap);
    if(name == NULL) {
        PyErr_SetString(state->CrustyException, "tilemap_tilemap_name failed");
        return(NULL);
    }

    return(PyUnicode_FromString(name));
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

    if(nargs == 0) {
        x = 0; y = 0; w = 0; h = 0;
    } else if(nargs < 4) {
        PyErr_SetString(PyExc_TypeError, "function needs 0 or at least 4 argument");
        return(NULL);
    } else {
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
    }

    if(tilemap_update_tilemap(self->ll->ll, self->tilemap, x, y, w, h) < 0) {
        PyErr_SetString(state->CrustyException, "tilemap_update_tilemap failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Tilemap_copy(TilemapObject *self,
                              PyTypeObject *defining_class,
                              PyObject *const *args,
                              Py_ssize_t nargs,
                              PyObject *kwnames) {
    unsigned long x, y, w, h, dx, dy;
    int valid_outside_copy;

    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Tilemap is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 6) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 4 argument");
        return(NULL);
    } else if(nargs == 6) {
        valid_outside_copy = 1;
    } else {
        valid_outside_copy = PyObject_RichCompareBool(args[6], Py_True, Py_EQ);
        if(valid_outside_copy < 0) {
            return(NULL);
        }
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
    dx = PyLong_AsUnsignedLong(args[4]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
    dy = PyLong_AsUnsignedLong(args[5]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    if(tilemap_copy_block(self->ll->ll, self->tilemap,
                          x, y, w, h, dx, dy,
                          valid_outside_copy) < 0) {
        PyErr_SetString(state->CrustyException, "tilemap_copy_block failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *LayerList_TM_layer(TilemapObject *self,
                                    PyTypeObject *defining_class,
                                    PyObject *const *args,
                                    Py_ssize_t nargs,
                                    PyObject *kwnames) {
    PyObject *arglist;
    PyObject *layer;

    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Tilemap is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }

    arglist = PyTuple_Pack(3, self->ll, self, args[0]);
    if(arglist == NULL) {
        return(NULL);
    }
    layer = PyObject_CallObject((PyObject *)(state->LayerType), arglist);
    Py_DECREF(arglist);
    if(layer == NULL) {
        return(NULL);
    }

    return(layer);
}

static PyMethodDef Tilemap_methods[] = {
    {
        "name",
        (PyCMethod) Tilemap_tilemap_name,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Get the tilemap name.\n\n"
        "name(...) -> name\n"
        "name  The tilemap's name."},
    {
        "tileset",
        (PyCMethod) Tilemap_set_tileset,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set a tileset which will be used for rendering out the tilemap.\n\n"
        "tileset(tileset)\n"
        "tileset  The Tileset."},
    {
        "map",
        (PyCMethod) Tilemap_set_map,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Update a rectangle section of the tilemap.\n\n"
        "map(x, y, pitch, width, height, buffer)\n"
        "x       Where to start updating from the left.\n"
        "y       Where to start updating from the top.\n"
        "pitch   How many items to advance each row.\n"
        "width   How wide of a rectangle to update.\n"
        "height  How tall of a rectangle to update.\n"
        "buffer  The buffer. (array.array, ndarray, etc)"},
    {
        "attr_flags",
        (PyCMethod) Tilemap_set_attr_flags,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Add/update attribute flags to a tilemap.\n\n"
        "attr_flags(x, y, pitch, width, height, buffer)\n"
        "x       Where to start updating from the left.\n"
        "y       Where to start updating from the top.\n"
        "pitch   How many items to advance each row.\n"
        "width   How wide of a rectangle to update.\n"
        "height  How tall of a rectangle to update.\n"
        "buffer  The buffer. (array.array, ndarray, etc)"},
    {
        "attr_colormod",
        (PyCMethod) Tilemap_set_attr_colormod,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Add/update colormod values for a tilemap.\n\n"
        "attr_colormod(x, y, pitch, width, height, buffer)\n"
        "x       Where to start updating from the left.\n"
        "y       Where to start updating from the top.\n"
        "pitch   How many items to advance each row.\n"
        "width   How wide of a rectangle to update.\n"
        "height  How tall of a rectangle to update.\n"
        "buffer  The buffer. (array.array, ndarray, etc)"},
    {
        "update",
        (PyCMethod) Tilemap_update,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Redraw a region of the tilemap.\n\n"
        "update()\n"
        "    Update the whole thing.\n"
        "update(x, y, width, height)\n"
        "x       Where to start updating from the left.\n"
        "y       Where to start updating from the top.\n"
        "width   How wide of a rectangle to update.\n"
        "height  How tall of a rectangle to update."},
    {
        "copy",
        (PyCMethod) Tilemap_copy,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Copy a block of a tilemap.\n\n"
        "copy(x, y, width, height, dx, dy)\n"
        "x                   Where to start copying from from the left.\n"
        "y                   Where to start copying from from the top.\n"
        "width               How wide of a rectangle to copy.\n"
        "height              How tall of a rectangle to copy.\n"
        "dx                  Where to start copying to from the left.\n"
        "dy                  Where to start copying to from the top.\n"
        "valid_outside_copy  Whether the contents outside of the copy region should be\n"
        "                    kept. Optional: defaults to True."},
    {
        "layer",
        (PyCMethod) LayerList_TM_layer,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Convenience method to create a Layer from this Tilemap.\n\n"
        "layer()"},
    {NULL}
};

static PyType_Slot TilemapSlots[] = {
    {Py_tp_doc, "A Tilemap.\n\n"
                "Tilemap(layerlist, tileset, width, height, name)\n"
                "layerlist   A LayerList\n"
                "tileset     The Tileset this tilemap will refer to\n"
                "width       The width of the tilemap in tiles.\n"
                "height      The height of the tilemap in tiles.\n"
                "name        Optional name or None"},
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
    self->tex = NULL;
    self->relative = NULL;
    self->layer = -1;

    return((PyObject *)self);
}

static int Layer_init(LayerObject *self, PyObject *args, PyObject *kwds) {
    PyObject *tmtex = NULL;
    PyObject *name = NULL;
    const char *cname;
    int tilemap = -1;
    SDL_Texture *tex = NULL;

    if(self->ll != NULL) {
        PyErr_SetString(PyExc_TypeError, "Layer already initialized");
        return(-1);
    }

    crustygame_state *state = PyType_GetModuleState(Py_TYPE(self));

    if(!PyArg_ParseTuple(args, "OOO", &(self->ll), &tmtex, &name)) {
        self->ll = NULL;
        return(-1);
    }
    Py_XINCREF(self->ll);
    Py_XINCREF(tmtex);
    Py_XINCREF(name);
    if(!PyObject_TypeCheck(self->ll, state->LayerListType)) {
        PyErr_SetString(PyExc_TypeError, "first argument must be a LayerList");
        goto error;
    }

    if(tmtex == Py_None) {
        Py_CLEAR(tmtex);
        tilemap = -1;
    } else if(PyObject_TypeCheck(tmtex, state->TilemapType)) {
        self->tm = (TilemapObject *)tmtex;
        tilemap = self->tm->tilemap;
    } else if(PyObject_TypeCheck(tmtex, state->LP_SDL_Texture)) {
        self->tex = tmtex;
        tex = get_value_from_lp_object(state, self->tex);
        if(tex == NULL) {
            PyErr_SetString(PyExc_RuntimeError, "couldn't get pointer of SDL_Texture");
            goto error;
        }
    } else {
        PyErr_SetString(PyExc_TypeError, "second argument must be either a Tilemap or a SDL_Texture or None");
        goto error;
    }

    if(name == Py_None) {
        cname = NULL;
    } else {
        cname = PyUnicode_AsUTF8(name);
        if(cname == NULL) {
            goto error;
        }
    }

    self->layer = tilemap_add_layer(self->ll->ll, tilemap, tex, cname);
    Py_CLEAR(name);
    if(self->layer < 0) {
        PyErr_SetString(state->CrustyException, "tilemap_add_layer failed");
        goto error;
    }

    return(0);

error:
    Py_XDECREF(name);
    self->tex = NULL;
    self->tm = NULL;
    Py_XDECREF(tmtex);
    Py_CLEAR(self->ll);
    return(-1);
}

static void Layer_dealloc(LayerObject *self) {
    if(self->layer >= 0) {
        tilemap_free_layer(self->ll->ll, self->layer);
    }
    Py_XDECREF(self->tex);
    Py_XDECREF(self->tm);
    Py_XDECREF(self->ll);
    Py_TYPE(self)->tp_free((PyObject *) self);
}

static PyObject *Tilemap_layer_name(LayerObject *self,
                                    PyTypeObject *defining_class,
                                    PyObject *const *args,
                                    Py_ssize_t nargs,
                                    PyObject *kwnames) {
    const char *name;

    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Layer is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    name = tilemap_layer_name(self->ll->ll, self->layer);
    if(name == NULL) {
        PyErr_SetString(state->CrustyException, "tilemap_layer_name failed");
        return(NULL);
    }

    return(PyUnicode_FromString(name));
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
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
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
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
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
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
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

static PyObject *Tilemap_set_layer_relative(LayerObject *self,
                                            PyTypeObject *defining_class,
                                            PyObject *const *args,
                                            Py_ssize_t nargs,
                                            PyObject *kwnames) {
    LayerObject *pylayer = NULL;
    int layer;

    if(self->ll == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Layer is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    if(args[0] == Py_None) {
        /* already NULL */
        layer = -1;
    } else if(PyObject_TypeCheck(args[0], state->LayerType)) {
        pylayer = ((LayerObject *)args[0]);
        layer = pylayer->layer;
    } else {
        PyErr_SetString(PyExc_TypeError, "relative layer type must be a Layer");
        return(NULL);
    }

    if(tilemap_set_layer_relative(self->ll->ll, self->layer, layer) < 0) {
        PyErr_SetString(state->CrustyException, "tilemap_set_layer_relative failed");
        return(NULL);
    }

    Py_XDECREF(self->relative);
    self->relative = pylayer;
    Py_XINCREF(self->relative);

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
        "name",
        (PyCMethod) Tilemap_layer_name,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Get the layer name.\n\n"
        "name(...) -> name\n"
        "name  The layer's name."},
    {
        "pos",
        (PyCMethod) Tilemap_set_layer_pos,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the on-screen position to draw the layer to.\n\n"
        "pos(x, y)\n"
        "x  Position from the left of the screen/relative layer.\n"
        "y  Position from the top of the screen/relative layer."},
    {
        "window",
        (PyCMethod) Tilemap_set_layer_window,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the window size of the view in to the tilemap to show.\n\n"
        "window(w, h)\n"
        "w  Width of the window\n"
        "h  Height of the window"},
    {
        "scroll_pos",
        (PyCMethod) Tilemap_set_layer_scroll_pos,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the scroll position (top-left corner) of the tilemap to show.\n\n"
        "scroll_pos(x, y)\n"
        "x  Position from the left of the tilemap.\n"
        "y  Position from the top of the tilemap."},
    {
        "scale",
        (PyCMethod) Tilemap_set_layer_scale,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the scale of the layer.\n\n"
        "scale(x, y)\n"
        "x  Scale on the X (horizontal) axis.\n"
        "y  Scale on the Y (vertical) axis."},
    {
        "rotation_center",
        (PyCMethod) Tilemap_set_layer_rotation_center,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the point around which the layer is rotated.\n\n"
        "rotation_center(x, y)\n"
        "x  Position from the left of the layer to rotate around.\n"
        "y  Position from the top of the layer to rotate around."},
    {
        "rotation",
        (PyCMethod) Tilemap_set_layer_rotation,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the rotation of the layer, in degrees.\n\n"
        "rotation(angle)\n"
        "angle  angle of rotation in degrees."},
    {
        "colormod",
        (PyCMethod) Tilemap_set_layer_colormod,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the layer's colormod.\n\n"
        "colormod(colormod)\n"
        "colormod  An integer color value created using this module's shift/mask constants."},
    {
        "blendmode",
        (PyCMethod) Tilemap_set_layer_blendmode,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the layer blendmode.\n\n"
        "blendmode(blendmode)\n"
        "blendmode  A blendmode, from this module's blendmode constants."},
    {
        "relative",
        (PyCMethod) Tilemap_set_layer_relative,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set a layer for this layer's position and angle to be relative to.\n\n"
        "relative(layer)\n"
        "layer  The layer this should be positioned relative to."},
    {
        "draw",
        (PyCMethod) Tilemap_draw_layer,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Finally, draw a layer to the screen or render target.\n\n"
        "draw()"},
    {NULL}
};

static PyType_Slot LayerSlots[] = {
    {Py_tp_doc, "A Layer.\n\n"
                "Tilemap(layerlist, gfx, name)\n"
                "layerlist  A LayerList\n"
                "gfx        A Tilemap, SDL_Texture or None for no graphics, useful for a relative reference point\n"
                "name       Optional name or None"},
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

static PyObject *Synth_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {
    SynthObject *self;

    self = (SynthObject *)type->tp_alloc(type, 0);
    if(self == NULL) {
        return(NULL);
    }
    /* just have it be do-nothing until it's properly initialize */
    self->s = NULL;
    self->log.cb = NULL;
    self->log.priv = NULL;
    self->synth_frame.cb = NULL;
    self->synth_frame.priv = NULL;
    self->channels = 0;
    self->outputBuffers = NULL;

    return((PyObject *)self);
}

static int Synth_init(SynthObject *self, PyObject *args, PyObject *kwds) {
    PyObject *fn = NULL;
    const char *filename;
    int opendev;
    PyObject *dn = NULL;
    const char *devname;
    unsigned int rate;
    unsigned int channels;
    unsigned int fragsize;
    SynthImportType format;
    PyObject *arglist;
    int i;

    if(self->s != NULL) {
        PyErr_SetString(PyExc_TypeError, "Synth already initialized");
        return(-1);
    }

    /* docs say this init isn't called if the class is instantiated as some
     * other type.  Not sure the consequences there... */
    crustygame_state *state = PyType_GetModuleState(Py_TYPE(self));

    if(!PyArg_ParseTuple(args, "OpOOOOOIIIi",
                         &fn, &opendev, &dn,
                         &(self->synth_frame.cb),
                         &(self->synth_frame.priv),
                         &(self->log.cb),
                         &(self->log.priv),
                         &rate, &channels, &fragsize, &format)) {
        self->synth_frame.cb = NULL;
        self->synth_frame.priv = NULL;
        self->log.cb = NULL;
        self->log.priv = NULL;
        return(-1);
    }
    Py_XINCREF(fn);
    Py_XINCREF(dn);
    Py_XINCREF(self->log.cb);
    Py_XINCREF(self->log.priv);
    Py_XINCREF(self->synth_frame.cb);
    Py_XINCREF(self->synth_frame.priv);

    if(!PyCallable_Check(self->log.cb)) {
        PyErr_SetString(PyExc_TypeError, "log_cb must be callable");
        goto error;
    }
    if(!PyCallable_Check(self->synth_frame.cb)) {
        PyErr_SetString(PyExc_TypeError, "synth_frame_cb must be callable");
        goto error;
    }

    if(fn == Py_None) {
        filename = NULL;
    } else {
        filename = PyUnicode_AsUTF8(fn);
        if(filename == NULL) {
            goto error;
        }
    }
    Py_CLEAR(fn);

    if(dn == Py_None) {
        devname = NULL;
    } else {
        devname = PyUnicode_AsUTF8(dn);
        if(devname == NULL) {
            goto error;
        }
    }
    Py_CLEAR(dn);

    self->s = synth_new(filename, opendev, devname,
                        (synth_frame_cb_t)synth_cb_adapter,
                        &(self->synth_frame),
                        (log_cb_return_t)log_cb_adapter,
                        &(self->log),
                        rate, channels, fragsize, format);
    if(self->s == NULL) {
        PyErr_SetString(state->CrustyException, "synth_new returned an error");
        goto error;
    }

    /* create output buffer objects for keeping track of them on this side */
    self->channels = synth_get_channels(self->s);
    if(self->channels < 1) {
        PyErr_SetString(state->CrustyException, "synth_get_channels returned an error");
        goto error;
    }

    self->outputBuffers = malloc(sizeof(BufferObject *) * self->channels);
    if(self->outputBuffers == NULL) {
        PyErr_SetString(PyExc_MemoryError, "couldn't allocate memory for output buffer objects");
        goto error;
    }
    for(i = 0; i < self->channels; i++) {
        self->outputBuffers[i] = NULL;
    }
    for(i = 0; i < self->channels; i++) {
        arglist = Py_BuildValue("OiIIO", self, SYNTH_TYPE_F32, i, 0, Py_None);
        if(arglist == NULL) {
            goto error;
        }
        self->outputBuffers[i] = (BufferObject *)PyObject_CallObject((PyObject *)(state->BufferType), arglist);
        Py_DECREF(arglist);
        if(self->outputBuffers[i] == NULL) {
            goto error;
        }
    }

    return(0);

error:
    if(self->outputBuffers != NULL) {
        for(i = 0; i < self->channels; i++) {
            if(self->outputBuffers[i] != NULL) {
                Py_CLEAR(self->outputBuffers[i]);
            }
        }
        free(self->outputBuffers);
        self->outputBuffers = NULL;
    }
    Py_CLEAR(self->synth_frame.priv);
    Py_CLEAR(self->synth_frame.cb);
    Py_CLEAR(self->log.priv);
    Py_CLEAR(self->log.cb);
    Py_CLEAR(dn);
    Py_CLEAR(fn);
    return(-1);
}

static void Synth_dealloc(SynthObject *self) {
    int i;

    if(self->outputBuffers != NULL) {
        for(i = 0; i < self->channels; i++) {
            if(self->outputBuffers[i] != NULL) {
                Py_CLEAR(self->outputBuffers[i]);
            }
        }
        free(self->outputBuffers);
        self->outputBuffers = NULL;
    }
    if(self->s != NULL) {
        synth_free(self->s);
    }
    Py_XDECREF(self->synth_frame.priv);
    Py_XDECREF(self->synth_frame.cb);
    Py_XDECREF(self->log.priv);
    Py_XDECREF(self->log.cb);
    Py_TYPE(self)->tp_free((PyObject *) self);
}

static PyObject *Synth_open_wav(SynthObject *self,
                                PyTypeObject *defining_class,
                                PyObject *const *args,
                                Py_ssize_t nargs,
                                PyObject *kwnames) {
    const char *filename;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    filename = PyUnicode_AsUTF8(args[0]);
    if(filename == NULL) {
        return(NULL);
    }

    if(synth_open_wav(self->s, filename) < 0) {
        PyErr_SetString(state->CrustyException, "synth_open_wave failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_close_wav(SynthObject *self,
                                 PyTypeObject *defining_class,
                                 PyObject *const *args,
                                 Py_ssize_t nargs,
                                 PyObject *kwnames) {
    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(synth_close_wav(self->s) < 0) {
        PyErr_SetString(state->CrustyException, "synth_close_wave failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_print_full_stats(SynthObject *self,
                                        PyTypeObject *defining_class,
                                        PyObject *const *args,
                                        Py_ssize_t nargs,
                                        PyObject *kwnames) {
    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    synth_print_full_stats(self->s);

    Py_RETURN_NONE;
}

static PyObject *Synth_set_enabled(SynthObject *self,
                                   PyTypeObject *defining_class,
                                   PyObject *const *args,
                                   Py_ssize_t nargs,
                                   PyObject *kwnames) {
    int enabled;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    enabled = PyObject_RichCompareBool(args[0], Py_True, Py_EQ);
    if(enabled < 0) {
        return(NULL);
    }

    if(synth_set_enabled(self->s, enabled) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_enabled failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_get_samples_needed(SynthObject *self,
                                          PyTypeObject *defining_class,
                                          PyObject *const *args,
                                          Py_ssize_t nargs,
                                          PyObject *kwnames) {
    int ret;
    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    ret = synth_get_samples_needed(self->s);
    if(ret < 0) {
        PyErr_SetString(state->CrustyException, "synth_get_samples_needed failed");
        return(NULL);
    }

    return(PyLong_FromLong(ret));
}

static PyObject *Synth_get_rate(SynthObject *self,
                                PyTypeObject *defining_class,
                                PyObject *const *args,
                                Py_ssize_t nargs,
                                PyObject *kwnames) {
    int ret;
    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    ret = synth_get_rate(self->s);
    if(ret < 0) {
        PyErr_SetString(state->CrustyException, "synth_get_rate failed");
        return(NULL);
    }

    return(PyLong_FromLong(ret));
}

static PyObject *Synth_get_channels(SynthObject *self,
                                    PyTypeObject *defining_class,
                                    PyObject *const *args,
                                    Py_ssize_t nargs,
                                    PyObject *kwnames) {
    int i, j;
    PyObject *ret;
    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    ret = PyTuple_New(self->channels);
    if(ret == NULL) {
        return(NULL);
    }
    /* increase the reference count to the objects about to be returned */
    for(i = 0; i < self->channels; i++) {
        Py_INCREF(self->outputBuffers[i]);
    }
    for(i = 0; i < self->channels; i++) {
        if(PyTuple_SetItem(ret, i, (PyObject *)(self->outputBuffers[i])) < 0) {
            for(j = 0; j < self->channels; j++) {
                Py_DECREF(self->outputBuffers[j]);
            }
            Py_DECREF(ret);
            return(NULL);
        }
    }

    return(ret);
}

static PyObject *Synth_get_fragment_size(SynthObject *self,
                                         PyTypeObject *defining_class,
                                         PyObject *const *args,
                                         Py_ssize_t nargs,
                                         PyObject *kwnames) {
    int ret;
    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    ret = synth_get_fragment_size(self->s);
    if(ret < 0) {
        PyErr_SetString(state->CrustyException, "synth_get_fragment_size failed");
        return(NULL);
    }

    return(PyLong_FromLong(ret));
}

static PyObject *Synth_has_underrun(SynthObject *self,
                                    PyTypeObject *defining_class,
                                    PyObject *const *args,
                                    Py_ssize_t nargs,
                                    PyObject *kwnames) {
    int ret;
    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    ret = synth_has_underrun(self->s);
    if(ret < 0) {
        PyErr_SetString(state->CrustyException, "synth_has_underrun failed");
        return(NULL);
    }

    return(PyBool_FromLong(ret));
}

static PyObject *Synth_frame(SynthObject *self,
                             PyTypeObject *defining_class,
                             PyObject *const *args,
                             Py_ssize_t nargs,
                             PyObject *kwnames) {
    int ret;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    ret = synth_frame(self->s);
    if(ret < 0) {
        PyErr_SetString(state->CrustyException, "synth_frame failed");
        return(NULL);
    }

    return(PyLong_FromLong(ret));
}

static PyObject *Synth_invalidate_buffers(SynthObject *self,
                                          PyTypeObject *defining_class,
                                          PyObject *const *args,
                                          Py_ssize_t nargs,
                                          PyObject *kwnames) {
    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    synth_invalidate_buffers(self->s);

    Py_RETURN_NONE;
}

static PyObject *Synth_set_fragments(SynthObject *self,
                                     PyTypeObject *defining_class,
                                     PyObject *const *args,
                                     Py_ssize_t nargs,
                                     PyObject *kwnames) {
    long fragments;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    fragments = PyLong_AsLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    if(synth_set_fragments(self->s, fragments) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_fragments failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_buffer(SynthObject *self,
                              PyTypeObject *defining_class,
                              PyObject *const *args,
                              Py_ssize_t nargs,
                              PyObject *kwnames) {
    PyObject *arglist;
    PyObject *buffer;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Tileset is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs == 2) {
        arglist = PyTuple_Pack(3, self, args[0], args[1]);
    } else if(nargs == 4) {
        arglist = PyTuple_Pack(5, self, args[0], args[1], args[2], args[3]);
    } else {
        PyErr_SetString(PyExc_TypeError, "this function needs 2 or 4 arguments");
        return(NULL);
    }
    if(arglist == NULL) {
        return(NULL);
    }
    buffer = PyObject_CallObject((PyObject *)(state->BufferType), arglist);
    Py_DECREF(arglist);
    if(buffer == NULL) {
        return(NULL);
    }

    return(buffer);
}

static PyMethodDef Synth_methods[] = {
    {
        "print_full_stats",
        (PyCMethod) Synth_print_full_stats,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Output information about the provided Synth structure.\n\n"
        "print_full_stats()"},
    {
        "open_wav",
        (PyCMethod) Synth_open_wav,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Open a WAV file for output on a currently running synthesizer.\n\n"
        "open_wav(filename)\n"
        "filename  WAV file to open and output to."},
    {
        "close_wav",
        (PyCMethod) Synth_close_wav,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Close an open WAV file.\n\n"
        "close_wav()"},
    {
        "enabled",
        (PyCMethod) Synth_set_enabled,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the enabled state of the synth.\n\n"
        "enabled(enabled)\n"
        "enabled  Boolean for whether the synth should enable."},
    {
        "needed",
        (PyCMethod) Synth_get_samples_needed,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Get the amount of samples necessary to top up the audio buffers.\n\n"
        "needed() -> needed\n"
        "needed  The amount of samples needed to fill the buffer."},
    {
        "rate",
        (PyCMethod) Synth_get_rate,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Get the sample rate the audio device was initialized with.\n\n"
        "rate() -> rate\n"
        "rate  Samples per second the audio is output at."},
    {
        "channels",
        (PyCMethod) Synth_get_channels,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Get the output channel objects for this Synth as a tuple.\n\n"
        "channels() -> channels\n"
        "channels  Number of output channels."},
    {
        "fragment_size",
        (PyCMethod) Synth_get_fragment_size,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Get the fragment size the audio device was initialized with.\n\n"
        "fragment_size() -> fragment_size\n"
        "fragment_size  Size of a fragment in samples."},
    {
        "underrun",
        (PyCMethod) Synth_has_underrun,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Returns whether the synth has underrun.\n\n"
        "underrun() -> underrun\n"
        "underrun  Boolean indicating if the audio output has underrun."},
    {
        "frame",
        (PyCMethod) Synth_frame,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Indicate that it's a good time for the frame callback to be run.\n\n"
        "frame() -> got\n"
        "got  Number of sampels generated."},
    {
        "invalidate_buffers",
        (PyCMethod) Synth_invalidate_buffers,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Invalidate the output buffers.\n\n"
        "invalidate_buffers()"},
    {
        "fragments",
        (PyCMethod) Synth_set_fragments,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the number of fragments that should be buffered internally.\n\n"
        "fragments(fragments)\n"
        "fragments  Number of fragments to buffer."},
    {
        "buffer",
        (PyCMethod) Synth_buffer,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Convenience function to create a buffer from this Synth.\n\n"
        "buffer(...) -> buffer\n"
        "...  See Buffer constructor, without the synth argument"},
    {NULL}
};

static PyType_Slot SynthSlots[] = {
    {Py_tp_doc, "A Synth.  Function arguments will be documented here but for more detailed\n"
                "documentation, see the HTML documentation.\n\n"
                "Synth(outfilename, opendev, devname, frame_cb, frame_priv, log_cb, log_priv, rate, channels, fragmentsize, format)\n"
                "outfilename   Optional filename which would be a WAV file opened and audio data output to.\n"
                "opendev       Whether an audio device should be opened.\n"
                "devname       Name of an SDL audio device or None to use default\n"
                "frame_cb      Function to call when audio data is being requested, which should return the number of samples emitted:"
                "                  frame_cb(frame_priv) -> samples\n"
                "frame_priv    Object which will be passed to frame_cb.\n"
                "log_cb        Function to call when the Synth needs to emit logs:"
                "                  log_cb(log_priv, message)\n"
                "log_priv      Object which will be passed to log_cb.\n"
                "rate          The rate to try to use.\n"
                "channels      The channel count to try to use.\n"
                "fragmentsize  The fragment size to try to use.\n"
                "format        The integer SDL_AudioFormat to try to use."},
    {Py_tp_new, Synth_new},
    {Py_tp_init, (initproc)Synth_init},
    {Py_tp_dealloc, (destructor)Synth_dealloc},
    {Py_tp_methods, Synth_methods},
    {Py_tp_traverse, heap_type_traverse},
    {0, NULL}
};

static PyType_Spec SynthSpec = {
    .name = "crustygame.Synth",
    .basicsize = sizeof(SynthObject),
    .itemsize = 0,
    .flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .slots = SynthSlots
};

static PyObject *Buffer_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {
    BufferObject *self;

    self = (BufferObject *)type->tp_alloc(type, 0);
    if(self == NULL) {
        return(NULL);
    }
    /* just have it be do-nothing until it's properly initialize */
    self->s = NULL;
    self->buffer = -1;
    self->rate = 0;

    return((PyObject *)self);
}

static int Buffer_init(BufferObject *self, PyObject *args, PyObject *kwds) {
    unsigned int type;
    const char *filename;
    PyObject *data = NULL;
    Py_buffer bufmem;
    Py_buffer *buf = NULL;
    unsigned int size = 0;
    PyObject *name = NULL;
    const char *cname;
    PyObject *etype, *evalue, *etraceback;

    if(self->s != NULL) {
        PyErr_SetString(PyExc_TypeError, "Buffer already initialized");
        return(-1);
    }

    /* docs say this init isn't called if the class is instantiated as some
     * other type.  Not sure the consequences there... */
    crustygame_state *state = PyType_GetModuleState(Py_TYPE(self));

    if(!PyArg_ParseTuple(args, "OIOIO",
                         &(self->s),
                         &type,
                         &data,
                         &size,
                         &name)) {
        self->s = NULL;
        PyErr_Fetch(&etype, &evalue, &etraceback);
        Py_XDECREF(etype);
        Py_XDECREF(evalue);
        Py_XDECREF(etraceback);

        if(!PyArg_ParseTuple(args, "OsO",
                            &(self->s),
                            &filename,
                            &name)) {
            self->s = NULL;
            return(-1);
        } else {
            Py_XINCREF(name);
            Py_XINCREF(self->s);

            if(name == Py_None) {
                cname = NULL;
            } else {
                cname = PyUnicode_AsUTF8(name);
                if(cname == NULL) {
                    goto error;
                }
            }

            self->buffer = synth_buffer_from_wav(self->s->s, filename, &(self->rate), cname);
            Py_CLEAR(name);
            if(self->buffer < 0) {
                PyErr_SetString(state->CrustyException, "synth_buffer_from_wav returned an error");
                goto error;
            }

            return(0);
        }
    }
    Py_XINCREF(name);
    Py_XINCREF(self->s);
    Py_XINCREF(data);

    if(!PyObject_TypeCheck(self->s, state->SynthType)) {
        PyErr_SetString(PyExc_TypeError, "first argument must be a Synth");
        goto error;
    }

    if(name == Py_None) {
        cname = NULL;
    } else {
        cname = PyUnicode_AsUTF8(name);
        if(cname == NULL) {
            goto error;
        }
    }

    self->rate = synth_get_rate(self->s->s);
    if(PyLong_Check(data)) {
        long buffer = PyLong_AsLong(data);
        /* for setting up output buffers */
        if(buffer >= self->s->channels) {
            PyErr_SetString(PyExc_ValueError, "Tried to make output buffer with index out of range");
            goto error;
        }
        self->buffer = buffer;
    } else if(data == Py_None) {
        /* silence buffers */
        self->buffer = synth_add_buffer(self->s->s, type, NULL, size, cname);
        Py_CLEAR(name);
        if(self->buffer < 0) {
            PyErr_SetString(state->CrustyException, "synth_add_buffer returned an error");
            goto error;
        }
    } else {
        buf = &bufmem;
        if(PyObject_GetBuffer(data, buf, PyBUF_CONTIG_RO) < 0) {
            buf = NULL;
            goto error;
        }

        if(size == 0) {
            /* length in samples */
            switch(type) {
                case SYNTH_TYPE_U8:
                    size = buf->len;
                    break;
                case SYNTH_TYPE_S16:
                    size = buf->len / sizeof(int16_t);
                    break;
                case SYNTH_TYPE_F32:
                    size = buf->len / sizeof(float);
                    break;
                case SYNTH_TYPE_F64:
                    size = buf->len / sizeof(double);
                    break;
                default:
                    PyErr_SetString(PyExc_ValueError, "Invalid buffer type.");
                    goto error;
            }
        } else {
            switch(type) {
                case SYNTH_TYPE_U8:
                    if(size > buf->len) {
                        PyErr_SetString(PyExc_ValueError, "size larger than buffer");
                        goto error;
                    }
                    break;
                case SYNTH_TYPE_S16:
                    if(size > buf->len / sizeof(int16_t)) {
                        PyErr_SetString(PyExc_ValueError, "size larger than buffer");
                        goto error;
                    }
                    break;
                case SYNTH_TYPE_F32:
                    if(size > buf->len / sizeof(float)) {
                        PyErr_SetString(PyExc_ValueError, "size larger than buffer");
                        goto error;
                    }
                    break;
                case SYNTH_TYPE_F64:
                    if(size > buf->len / sizeof(double)) {
                        PyErr_SetString(PyExc_ValueError, "size larger than buffer");
                        goto error;
                    }
                    break;
                default:
                    PyErr_SetString(PyExc_ValueError, "Invalid buffer type.");
                    goto error;
            }
        }

        self->buffer = synth_add_buffer(self->s->s, type, buf->buf, size, cname);
        Py_CLEAR(name);
        if(self->buffer < 0) {
            PyErr_SetString(state->CrustyException, "synth_add_buffer returned an error");
            goto error;
        }

        PyBuffer_Release(buf);
    }

    Py_XDECREF(data);
    return(0);

error:
    Py_XDECREF(name);
    if(buf != NULL) {
        PyBuffer_Release(buf);
    }
    Py_XDECREF(data);
    Py_CLEAR(self->s);
    return(-1);
}

static void Buffer_dealloc(BufferObject *self) {
    if(self->s != NULL && self->buffer >= self->s->channels) {
        synth_free_buffer(self->s->s, self->buffer);
    }
    Py_XDECREF(self->s);
    Py_TYPE(self)->tp_free((PyObject *) self);
}

static PyObject *Synth_get_size(BufferObject *self,
                                PyTypeObject *defining_class,
                                PyObject *const *args,
                                Py_ssize_t nargs,
                                PyObject *kwnames) {
    int ret;
    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Buffer is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    ret = synth_buffer_get_size(self->s->s, self->buffer);
    if(ret < 0) {
        PyErr_SetString(state->CrustyException, "synth_buffer_get_size failed");
        return(NULL);
    }

    return(PyLong_FromLong(ret));
}

static PyObject *Synth_buffer_get_rate(BufferObject *self,
                                       PyTypeObject *defining_class,
                                       PyObject *const *args,
                                       Py_ssize_t nargs,
                                       PyObject *kwnames) {
    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Buffer is not initialized");
        return(NULL);
    }

    return(PyLong_FromLong(self->rate));
}

static PyObject *Synth_silence_buffer(BufferObject *self,
                                      PyTypeObject *defining_class,
                                      PyObject *const *args,
                                      Py_ssize_t nargs,
                                      PyObject *kwnames) {
    unsigned int start;
    unsigned int length;
    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Buffer is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);
    if(nargs < 2) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 2 argument");
        return(NULL);
    }
    start = PyLong_AsLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }
    length = PyLong_AsLong(args[1]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    if(synth_silence_buffer(self->s->s, self->buffer, start, length) < 0) {
        PyErr_SetString(state->CrustyException, "synth_silence_buffer failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_B_player(BufferObject *self,
                                PyTypeObject *defining_class,
                                PyObject *const *args,
                                Py_ssize_t nargs,
                                PyObject *kwnames) {
    PyObject *arglist;
    PyObject *player;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Buffer is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }

    arglist = PyTuple_Pack(3, self->s, self, args[0]);
    if(arglist == NULL) {
        return(NULL);
    }
    player = PyObject_CallObject((PyObject *)(state->PlayerType), arglist);
    Py_DECREF(arglist);
    if(player == NULL) {
        return(NULL);
    }

    return(player);
}

static PyObject *Synth_B_filter(BufferObject *self,
                                PyTypeObject *defining_class,
                                PyObject *const *args,
                                Py_ssize_t nargs,
                                PyObject *kwnames) {
    PyObject *arglist;
    PyObject *filter;
    PyObject *zero = NULL;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Buffer is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs >= 2) {
        arglist = PyTuple_Pack(4, self->s, self, args[0], args[1]);
    } else if(nargs == 1) {
        zero = PyLong_FromLong(0);
        if(zero == NULL) {
            return(NULL);
        }
        arglist = PyTuple_Pack(4, self->s, self, args[0], zero);
    } else {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        goto error;
    }
    if(arglist == NULL) {
        goto error;
    }
    filter = PyObject_CallObject((PyObject *)(state->FilterType), arglist);
    Py_DECREF(arglist);
    if(filter == NULL) {
        goto error;
    }

    Py_XDECREF(zero);

    return(filter);

error:
    Py_XDECREF(zero);

    return(NULL);
}

static PyObject *Synth_internal(BufferObject *self,
                                PyTypeObject *defining_class,
                                PyObject *const *args,
                                Py_ssize_t nargs,
                                PyObject *kwnames) {
    PyObject *arglist;
    PyObject *internal;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Buffer is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    arglist = PyTuple_Pack(2, self->s, self);
    if(arglist == NULL) {
        return(NULL);
    }
    internal = PyObject_CallObject((PyObject *)(state->InternalBufferType), arglist);
    Py_DECREF(arglist);
    if(internal == NULL) {
        return(NULL);
    }

    return(internal);
}

static PyMethodDef Buffer_methods[] = {
    {
        "size",
        (PyCMethod) Synth_get_size,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Get the size in samples of a buffer.\n\n"
        "size() -> size\n"
        "size  The size of the buffer in samples."},
    {
        "rate",
        (PyCMethod) Synth_buffer_get_rate,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Get the sample rate of the buffer if loaded from a wav, otherwise, just the Synth's rate.\n\n"
        "rate() -> rate\n"
        "rate  The buffer's native sample rate."},
    {
        "silence",
        (PyCMethod) Synth_silence_buffer,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Silence a buffer which contains audio.\n\n"
        "silence(start, length)\n"
        "start   Sample to start silencing on.\n"
        "length  Number of samples to silence."},
    {
        "player",
        (PyCMethod) Synth_B_player,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Convenience function to make a player from this buffer.\n\n"
        "player(...) -> player\n"
        "...  See Player constructor, without synth or buffer arguments"},
    {
        "filter",
        (PyCMethod) Synth_B_filter,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Convenience function to make a filter from this buffer.\n\n"
        "filter(...) -> filter\n"
        "...  See Filter constructor, without synth or buffer arguments"},
    {
        "internal",
        (PyCMethod) Synth_internal,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Get an internal buffer handle from this buffer.\n"
        "NOTE: This is kinda janky as I don't really know how this works but it works so\n"
        "it probably won't change unless someone can really give me advice on making\n"
        "this better.\n\n"
        "internal() -> pybuffer\n"
        "pybuffer  Object which can interact with other PyBuffer objects like array.array, ndarray, etc."},
    {NULL}
};

static PyType_Slot BufferSlots[] = {
    {Py_tp_doc, "A Buffer.\n\n"
                "Buffer(synth, type, data, size, name)\n"
                "synth  A Synth\n"
                "type   The SDL_AudioFormat type of the data\n"
                "data   A buffer containing the data (array.array, ndarray, etc)\n"
                "size   The number of samples to use.\n"
                "name   Optional name or None\n\n"
                "Buffer(synth, type, None, size, name)\n"
                "    Make a empty buffer.\n"
                "synth  A Synth\n"
                "type   The SDL_AudioFormat type of the data\n"
                "size   The number of samples to use.\n"
                "name   Optional name or None\n\n"
                "Buffer(synth, None, channel, None, None)\n"
                "synth    A Synth\n"
                "channel  An output channel buffer number\n\n"
                "Buffer(synth, filename, name)\n"
                "synth     A Synth\n"
                "filename  A WAV file to load\n"
                "name      Optional name or None to use the filename"},
    {Py_tp_new, Buffer_new},
    {Py_tp_init, (initproc)Buffer_init},
    {Py_tp_dealloc, (destructor)Buffer_dealloc},
    {Py_tp_methods, Buffer_methods},
    {Py_tp_traverse, heap_type_traverse},
    {0, NULL}
};

static PyType_Spec BufferSpec = {
    .name = "crustygame.Buffer",
    .basicsize = sizeof(BufferObject),
    .itemsize = 0,
    .flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .slots = BufferSlots
};

static PyObject *InternalBuffer_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {
    InternalBufferObject *self;

    self = (InternalBufferObject *)type->tp_alloc(type, 0);
    if(self == NULL) {
        return(NULL);
    }
    /* just have it be do-nothing until it's properly initialize */
    self->s = NULL;
    self->b = NULL;

    return((PyObject *)self);
}

static int InternalBuffer_init(InternalBufferObject *self, PyObject *args, PyObject *kwds) {
    if(self->s != NULL) {
        PyErr_SetString(PyExc_TypeError, "InternalBuffer already initialized");
        return(-1);
    }

    /* docs say this init isn't called if the class is instantiated as some
     * other type.  Not sure the consequences there... */
    crustygame_state *state = PyType_GetModuleState(Py_TYPE(self));

    if(!PyArg_ParseTuple(args, "OO", &(self->s), &(self->b))) {
        self->s = NULL;
        self->b = NULL;
        return(-1);
    }
    Py_XINCREF(self->s);
    Py_XINCREF(self->b);
    if(!PyObject_TypeCheck(self->s, state->SynthType)) {
        PyErr_SetString(PyExc_TypeError, "first argument must be a Synth");
        goto error;
    }
    if(!PyObject_TypeCheck(self->b, state->BufferType)) {
        PyErr_SetString(PyExc_TypeError, "second argument must be a Buffer");
        goto error;
    }
    self->size = synth_get_internal_buffer(self->s->s, self->b->buffer, &(self->data));
    if(self->size < 0) {
        PyErr_SetString(PyExc_RuntimeError, "failed to get internal buffer pointer");
        goto error;
    }

    return(0);

error:
    Py_CLEAR(self->b);
    Py_CLEAR(self->s);
    return(-1);
}

static void InternalBuffer_dealloc(InternalBufferObject *self) {
    if(self->b != NULL) {
        synth_release_buffer(self->s->s, self->b->buffer);
    }
    Py_XDECREF(self->b);
    Py_XDECREF(self->s);
    Py_TYPE(self)->tp_free((PyObject *) self);
}

static Py_ssize_t InternalBuffer_length(InternalBufferObject *self) {
    return(self->size);
}

static int InternalBuffer_getbuffer(InternalBufferObject *self, Py_buffer *view, int flags) {
    if(self->s == NULL) {
        PyErr_SetString(PyExc_BufferError, "this Buffer is not initialized");
        return(-1);
    }

    Py_INCREF(self);
    view->obj = (void *)self;
    view->readonly = 0;
    view->itemsize = sizeof(float);
    if(flags & PyBUF_FORMAT) {
        view->format = "f";
    } else {
        view->format = NULL;
    }
    /* never needed here */
    view->suboffsets = NULL;
    view->len = self->size * view->itemsize;
    view->buf = self->data;
    view->ndim = 1;
    if((flags & PyBUF_ND) == PyBUF_ND) {
        view->shape = malloc(sizeof(Py_ssize_t));
        if(view->shape == NULL) {
            PyErr_SetString(PyExc_BufferError, "failed to allocate memory for shape");
            goto error;
        }
        view->shape[0] = self->size;
        if((flags & PyBUF_STRIDES) == PyBUF_STRIDES) {
            view->strides = malloc(sizeof(Py_ssize_t));
            if(view->strides == NULL) {
                PyErr_SetString(PyExc_BufferError, "failed to allocate memory for shape");
                goto error;
            }
            view->strides[0] = sizeof(float);
        } else {
            view->strides = NULL;
        }
    } else {
        view->shape = NULL;
    }

    return(0);

error:
    Py_DECREF(self);
    view->obj = NULL;
    return(-1);
}

static void InternalBuffer_releasebuffer(InternalBufferObject *self, Py_buffer *view) {
    return;
}

static PyType_Slot InternalBufferSlots[] = {
    {Py_tp_doc, "A InternalBuffer.\n\n"
                "InternalBuffer(synth, buffer)\n"
                "synth   A Synth\n"
                "buffer  A Buffer"},
    {Py_tp_new, InternalBuffer_new},
    {Py_tp_init, (initproc)InternalBuffer_init},
    {Py_tp_dealloc, (destructor)InternalBuffer_dealloc},
    {Py_tp_traverse, heap_type_traverse},
    {Py_sq_length, (lenfunc)InternalBuffer_length},
    {Py_bf_getbuffer, (getbufferproc)InternalBuffer_getbuffer},
    {Py_bf_releasebuffer, (releasebufferproc)InternalBuffer_releasebuffer},
    {0, NULL}
};

static PyType_Spec InternalBufferSpec = {
    .name = "crustygame.InternalBuffer",
    .basicsize = sizeof(InternalBufferObject),
    .itemsize = 0,
    .flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .slots = InternalBufferSlots
};

static PyObject *Player_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {
    PlayerObject *self;

    self = (PlayerObject *)type->tp_alloc(type, 0);
    if(self == NULL) {
        return(NULL);
    }
    /* just have it be do-nothing until it's properly initialize */
    self->s = NULL;
    self->inBuffer = NULL;
    self->outBuffer = NULL;
    self->volBuffer = NULL;
    self->startBuffer = NULL;
    self->lengthBuffer = NULL;
    self->phaseBuffer = NULL;
    self->speedBuffer = NULL;
    self->player = -1;

    return((PyObject *)self);
}

static int Player_init(PlayerObject *self, PyObject *args, PyObject *kwds) {
    BufferObject *buffer = NULL;
    PyObject *name = NULL;
    const char *cname;

    if(self->s != NULL) {
        PyErr_SetString(PyExc_TypeError, "Player already initialized");
        return(-1);
    }

    /* docs say this init isn't called if the class is instantiated as some
     * other type.  Not sure the consequences there... */
    crustygame_state *state = PyType_GetModuleState(Py_TYPE(self));

    if(!PyArg_ParseTuple(args, "OOO",
                         &(self->s),
                         &buffer,
                         &name)) {
        self->s = NULL;
        return(-1);
    }
    Py_XINCREF(name);
    Py_XINCREF(self->s);
    Py_XINCREF(buffer);
    if(!PyObject_TypeCheck(self->s, state->SynthType)) {
        PyErr_SetString(PyExc_TypeError, "first argument must be a Synth");
        goto error;
    }
    if(!PyObject_TypeCheck(buffer, state->BufferType)) {
        PyErr_SetString(PyExc_TypeError, "second argument must be a Buffer");
        goto error;
    }
    /* reflect all the buffers which are referenced internally */
    self->inBuffer = buffer;
    Py_XINCREF(self->inBuffer);
    self->outBuffer = self->s->outputBuffers[0];
    Py_XINCREF(self->outBuffer);
    self->volBuffer = buffer;
    Py_XINCREF(self->volBuffer);
    self->startBuffer = buffer;
    Py_XINCREF(self->startBuffer);
    self->lengthBuffer = buffer;
    Py_XINCREF(self->lengthBuffer);
    self->phaseBuffer = buffer;
    Py_XINCREF(self->phaseBuffer);
    self->speedBuffer = buffer;
    Py_XINCREF(self->speedBuffer);
    Py_CLEAR(buffer);

    if(name == Py_None) {
        cname = NULL;
    } else {
        cname = PyUnicode_AsUTF8(name);
        if(cname == NULL) {
            goto error;
        }
    }

    self->player = synth_add_player(self->s->s, self->inBuffer->buffer, cname);
    Py_CLEAR(name);
    if(self->player < 0) {
        PyErr_SetString(state->CrustyException, "synth_add_player returned an error");
        goto error;
    }

    return(0);

error:
    Py_XDECREF(name);
    Py_CLEAR(self->speedBuffer);
    Py_CLEAR(self->phaseBuffer);
    Py_CLEAR(self->lengthBuffer);
    Py_CLEAR(self->startBuffer);
    Py_CLEAR(self->volBuffer);
    Py_CLEAR(self->outBuffer);
    Py_CLEAR(self->inBuffer);
    Py_CLEAR(buffer);
    Py_CLEAR(self->s);
    return(-1);
}

static void Player_dealloc(PlayerObject *self) {
    if(self->player >= 0) {
        synth_free_player(self->s->s, self->player);
    }
    Py_XDECREF(self->speedBuffer);
    Py_XDECREF(self->phaseBuffer);
    Py_XDECREF(self->lengthBuffer);
    Py_XDECREF(self->startBuffer);
    Py_XDECREF(self->volBuffer);
    Py_XDECREF(self->outBuffer);
    Py_XDECREF(self->inBuffer);
    Py_XDECREF(self->s);
    Py_TYPE(self)->tp_free((PyObject *) self);
}

static PyObject *Synth_set_player_input_buffer(PlayerObject *self,
                                               PyTypeObject *defining_class,
                                               PyObject *const *args,
                                               Py_ssize_t nargs,
                                               PyObject *kwnames) {
    BufferObject *buffer;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    if(!PyObject_TypeCheck(args[0], state->BufferType)) {
        PyErr_SetString(PyExc_TypeError, "first argument must be a Buffer");
        return(NULL);
    }
    buffer = (BufferObject *)(args[0]);

    if(synth_set_player_input_buffer(self->s->s, self->player, buffer->buffer) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_player_input_buffer failed");
        return(NULL);
    }
    Py_DECREF(self->inBuffer);
    self->inBuffer = buffer;
    Py_INCREF(self->inBuffer);

    Py_RETURN_NONE;
}

static PyObject *Synth_set_player_input_buffer_pos(PlayerObject *self,
                                                   PyTypeObject *defining_class,
                                                   PyObject *const *args,
                                                   Py_ssize_t nargs,
                                                   PyObject *kwnames) {
    float pos;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    pos = (float)PyFloat_AsDouble(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    if(synth_set_player_input_buffer_pos(self->s->s, self->player, pos) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_player_input_buffer_pos failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_set_player_output_buffer(PlayerObject *self,
                                                PyTypeObject *defining_class,
                                                PyObject *const *args,
                                                Py_ssize_t nargs,
                                                PyObject *kwnames) {
    BufferObject *buffer;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    if(!PyObject_TypeCheck(args[0], state->BufferType)) {
        PyErr_SetString(PyExc_TypeError, "first argument must be a Buffer");
        return(NULL);
    }
    buffer = (BufferObject *)(args[0]);

    if(synth_set_player_output_buffer(self->s->s, self->player, buffer->buffer) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_player_output_buffer failed");
        return(NULL);
    }
    Py_DECREF(self->outBuffer);
    self->outBuffer = buffer;
    Py_INCREF(self->outBuffer);

    Py_RETURN_NONE;
}

static PyObject *Synth_set_player_output_buffer_pos(PlayerObject *self,
                                                    PyTypeObject *defining_class,
                                                    PyObject *const *args,
                                                    Py_ssize_t nargs,
                                                    PyObject *kwnames) {
    int pos;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    pos = PyLong_AsLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    if(synth_set_player_output_buffer_pos(self->s->s, self->player, pos) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_player_output_buffer_pos failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_set_player_output_mode(PlayerObject *self,
                                              PyTypeObject *defining_class,
                                              PyObject *const *args,
                                              Py_ssize_t nargs,
                                              PyObject *kwnames) {
    int mode;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    mode = PyLong_AsLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    if(synth_set_player_output_mode(self->s->s, self->player, mode) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_player_output_mode failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_set_player_volume_mode(PlayerObject *self,
                                              PyTypeObject *defining_class,
                                              PyObject *const *args,
                                              Py_ssize_t nargs,
                                              PyObject *kwnames) {
    int mode;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    mode = PyLong_AsLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    if(synth_set_player_volume_mode(self->s->s, self->player, mode) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_player_volume_mode failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_set_player_volume(PlayerObject *self,
                                         PyTypeObject *defining_class,
                                         PyObject *const *args,
                                         Py_ssize_t nargs,
                                         PyObject *kwnames) {
    float volume;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    volume = (float)PyFloat_AsDouble(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    if(synth_set_player_volume(self->s->s, self->player, volume) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_player_volumefailed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_set_player_volume_source(PlayerObject *self,
                                                PyTypeObject *defining_class,
                                                PyObject *const *args,
                                                Py_ssize_t nargs,
                                                PyObject *kwnames) {
    BufferObject *buffer;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    if(!PyObject_TypeCheck(args[0], state->BufferType)) {
        PyErr_SetString(PyExc_TypeError, "first argument must be a Buffer");
        return(NULL);
    }
    buffer = (BufferObject *)(args[0]);

    if(synth_set_player_volume_source(self->s->s, self->player, buffer->buffer) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_player_volume_source failed");
        return(NULL);
    }
    Py_DECREF(self->volBuffer);
    self->volBuffer = buffer;
    Py_INCREF(self->volBuffer);

    Py_RETURN_NONE;
}

static PyObject *Synth_set_player_mode(PlayerObject *self,
                                       PyTypeObject *defining_class,
                                       PyObject *const *args,
                                       Py_ssize_t nargs,
                                       PyObject *kwnames) {
    int mode;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    mode = PyLong_AsLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    if(synth_set_player_mode(self->s->s, self->player, mode) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_player_mode failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_set_player_loop_start(PlayerObject *self,
                                             PyTypeObject *defining_class,
                                             PyObject *const *args,
                                             Py_ssize_t nargs,
                                             PyObject *kwnames) {
    int pos;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    pos = PyLong_AsLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    if(synth_set_player_loop_start(self->s->s, self->player, pos) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_player_loop_start failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_set_player_loop_length(PlayerObject *self,
                                              PyTypeObject *defining_class,
                                              PyObject *const *args,
                                              Py_ssize_t nargs,
                                              PyObject *kwnames) {
    unsigned int length;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    length = PyLong_AsUnsignedLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    if(synth_set_player_loop_length(self->s->s, self->player, length) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_player_loop_length failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_set_player_start_source(PlayerObject *self,
                                               PyTypeObject *defining_class,
                                               PyObject *const *args,
                                               Py_ssize_t nargs,
                                               PyObject *kwnames) {
    BufferObject *buffer;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    if(!PyObject_TypeCheck(args[0], state->BufferType)) {
        PyErr_SetString(PyExc_TypeError, "first argument must be a Buffer");
        return(NULL);
    }
    buffer = (BufferObject *)(args[0]);

    if(synth_set_player_start_source(self->s->s, self->player, buffer->buffer) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_player_start_source failed");
        return(NULL);
    }
    Py_DECREF(self->startBuffer);
    self->startBuffer = buffer;
    Py_INCREF(self->startBuffer);

    Py_RETURN_NONE;
}

static PyObject *Synth_set_player_start_values(PlayerObject *self,
                                               PyTypeObject *defining_class,
                                               PyObject *const *args,
                                               Py_ssize_t nargs,
                                               PyObject *kwnames) {
    unsigned int values;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    values = PyLong_AsUnsignedLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    if(synth_set_player_start_values(self->s->s, self->player, values) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_player_start_values failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_set_player_start_granularity(PlayerObject *self,
                                                    PyTypeObject *defining_class,
                                                    PyObject *const *args,
                                                    Py_ssize_t nargs,
                                                    PyObject *kwnames) {
    unsigned int granularity;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    granularity = PyLong_AsUnsignedLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    if(synth_set_player_start_values(self->s->s, self->player, granularity) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_player_start_granularity failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_set_player_start_mode(PlayerObject *self,
                                             PyTypeObject *defining_class,
                                             PyObject *const *args,
                                             Py_ssize_t nargs,
                                             PyObject *kwnames) {
    int mode;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    mode = PyLong_AsLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    if(synth_set_player_start_mode(self->s->s, self->player, mode) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_player_start_mode failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_set_player_length_source(PlayerObject *self,
                                                PyTypeObject *defining_class,
                                                PyObject *const *args,
                                                Py_ssize_t nargs,
                                                PyObject *kwnames) {
    BufferObject *buffer;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    if(!PyObject_TypeCheck(args[0], state->BufferType)) {
        PyErr_SetString(PyExc_TypeError, "first argument must be a Buffer");
        return(NULL);
    }
    buffer = (BufferObject *)(args[0]);

    if(synth_set_player_length_source(self->s->s, self->player, buffer->buffer) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_player_length_source failed");
        return(NULL);
    }
    Py_DECREF(self->lengthBuffer);
    self->lengthBuffer = buffer;
    Py_INCREF(self->lengthBuffer);

    Py_RETURN_NONE;
}

static PyObject *Synth_set_player_length_values(PlayerObject *self,
                                                PyTypeObject *defining_class,
                                                PyObject *const *args,
                                                Py_ssize_t nargs,
                                                PyObject *kwnames) {
    unsigned int values;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    values = PyLong_AsUnsignedLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    if(synth_set_player_length_values(self->s->s, self->player, values) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_player_length_values failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_set_player_length_granularity(PlayerObject *self,
                                                     PyTypeObject *defining_class,
                                                     PyObject *const *args,
                                                     Py_ssize_t nargs,
                                                     PyObject *kwnames) {
    unsigned int granularity;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    granularity = PyLong_AsUnsignedLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    if(synth_set_player_length_values(self->s->s, self->player, granularity) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_player_length_granularity failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_set_player_length_mode(PlayerObject *self,
                                              PyTypeObject *defining_class,
                                              PyObject *const *args,
                                              Py_ssize_t nargs,
                                              PyObject *kwnames) {
    int mode;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    mode = PyLong_AsLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    if(synth_set_player_length_mode(self->s->s, self->player, mode) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_player_length_mode failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_set_player_phase_source(PlayerObject *self,
                                               PyTypeObject *defining_class,
                                               PyObject *const *args,
                                               Py_ssize_t nargs,
                                               PyObject *kwnames) {
    BufferObject *buffer;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    if(!PyObject_TypeCheck(args[0], state->BufferType)) {
        PyErr_SetString(PyExc_TypeError, "first argument must be a Buffer");
        return(NULL);
    }
    buffer = (BufferObject *)(args[0]);

    if(synth_set_player_phase_source(self->s->s, self->player, buffer->buffer) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_player_phase_source failed");
        return(NULL);
    }
    Py_DECREF(self->phaseBuffer);
    self->phaseBuffer = buffer;
    Py_INCREF(self->phaseBuffer);

    Py_RETURN_NONE;
}

static PyObject *Synth_set_player_speed_mode(PlayerObject *self,
                                             PyTypeObject *defining_class,
                                             PyObject *const *args,
                                             Py_ssize_t nargs,
                                             PyObject *kwnames) {
    int mode;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    mode = PyLong_AsLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    if(synth_set_player_speed_mode(self->s->s, self->player, mode) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_player_speed_mode failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_set_player_speed(PlayerObject *self,
                                        PyTypeObject *defining_class,
                                        PyObject *const *args,
                                        Py_ssize_t nargs,
                                        PyObject *kwnames) {
    float speed;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    speed = (float)PyFloat_AsDouble(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    if(synth_set_player_speed(self->s->s, self->player, speed) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_player_speed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_set_player_speed_source(PlayerObject *self,
                                               PyTypeObject *defining_class,
                                               PyObject *const *args,
                                               Py_ssize_t nargs,
                                               PyObject *kwnames) {
    BufferObject *buffer;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    if(!PyObject_TypeCheck(args[0], state->BufferType)) {
        PyErr_SetString(PyExc_TypeError, "first argument must be a Buffer");
        return(NULL);
    }
    buffer = (BufferObject *)(args[0]);

    if(synth_set_player_speed_source(self->s->s, self->player, buffer->buffer) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_player_speed_source failed");
        return(NULL);
    }
    Py_DECREF(self->speedBuffer);
    self->speedBuffer = buffer;
    Py_INCREF(self->speedBuffer);

    Py_RETURN_NONE;
}

static PyObject *Synth_run_player(PlayerObject *self,
                                  PyTypeObject *defining_class,
                                  PyObject *const *args,
                                  Py_ssize_t nargs,
                                  PyObject *kwnames) {
    unsigned int req;
    int ret;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    req = PyLong_AsUnsignedLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    ret = synth_run_player(self->s->s, self->player, req);
    if(ret < 0) {
        PyErr_SetString(state->CrustyException, "synth_run_player failed");
        return(NULL);
    }

    return(PyLong_FromLong(ret));
}

static PyObject *Synth_player_stopped_reason(PlayerObject *self,
                                             PyTypeObject *defining_class,
                                             PyObject *const *args,
                                             Py_ssize_t nargs,
                                             PyObject *kwnames) {
    int ret;
    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Buffer is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    ret = synth_player_stopped_reason(self->s->s, self->player);
    if(ret < 0) {
        PyErr_SetString(state->CrustyException, "synth_player_stopped_reason failed");
        return(NULL);
    }

    return(PyLong_FromLong(ret));
}

static PyMethodDef Player_methods[] = {
    {
        "input",
        (PyCMethod) Synth_set_player_input_buffer,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the input buffer for the player.\n\n"
        "input(buffer)\n"
        "buffer  Buffer to be this Player's input."},
    {
        "input_pos",
        (PyCMethod) Synth_set_player_input_buffer_pos,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the position in samples that the input buffer should start playing from.\n\n"
        "input_pos(pos)\n"
        "pos  Position to start playing from."},
    {
        "output",
        (PyCMethod) Synth_set_player_output_buffer,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set a buffer to output to.\n\n"
        "output(buffer)\n"
        "buffer  Buffer to be this Player's output."},
    {
        "output_pos",
        (PyCMethod) Synth_set_player_output_buffer_pos,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the output buffer position.\n\n"
        "output_pos(pos)\n"
        "pos  Position to start output to."},
    {
        "output_mode",
        (PyCMethod) Synth_set_player_output_mode,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the output mode or operation for the player.\n\n"
        "output_mode(mode)\n"
        "mode  Output mode from one of the output mode constants."},
    {
        "volume_mode",
        (PyCMethod) Synth_set_player_volume_mode,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the volume mode.\n\n"
        "volume_mode(mode)\n"
        "mode  Volume mode from one of the auto constants."},
    {
        "volume",
        (PyCMethod) Synth_set_player_volume,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the constant player volume.\n\n"
        "volume(vol)\n"
        "vol  The base output volume."},
    {
        "volume_source",
        (PyCMethod) Synth_set_player_volume_source,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the player volume source.\n\n"
        "volume_source(buffer)\n"
        "buffer  The buffer used for modulating the volume."},
    {
        "mode",
        (PyCMethod) Synth_set_player_mode,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the playback mode for the player.\n\n"
        "mode(mode)\n"
        "mode  The playback mode from the player mode constants."},
    {
        "loop_start",
        (PyCMethod) Synth_set_player_loop_start,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set loop start or phase source start position.\n\n"
        "loop_start(pos)\n"
        "pos  The loop start position."},
    {
        "loop_length",
        (PyCMethod) Synth_set_player_loop_length,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set loop length or phase source 1.0 position.\n\n"
        "loop_length(pos)\n"
        "pos  The loop length."},
    {
        "start_source",
        (PyCMethod) Synth_set_player_start_source,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the source buffer for start position automation.\n\n"
        "start_source(buffer)\n"
        "buffer  The buffer used for modulating the start position."},
    {
        "start_values",
        (PyCMethod) Synth_set_player_start_values,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the number of discrete values to fall on.\n\n"
        "start_values(values)\n"
        "values  The number of values."},
    {
        "start_granularity",
        (PyCMethod) Synth_set_player_start_granularity,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the positional granularity or distance between values\n\n"
        "start_granularity(granularity)\n"
        "granularity  The distance between values."},
    {
        "start_mode",
        (PyCMethod) Synth_set_player_start_mode,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Mode for loop start position automation.\n\n"
        "start_mode(mode)\n"
        "mode  The start mode."},
    {
        "length_source",
        (PyCMethod) Synth_set_player_length_source,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the source buffer for length automation.\n\n"
        "length_source(buffer)\n"
        "buffer  The buffer used for modulating the length."},
    {
        "length_values",
        (PyCMethod) Synth_set_player_length_values,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the number of discrete values to fall on.\n\n"
        "length_values(values)\n"
        "values  The number of values."},
    {
        "length_granularity",
        (PyCMethod) Synth_set_player_length_granularity,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the positional granularity or distance between values\n\n"
        "length_granularity(granularity)\n"
        "granularity  The distance between values."},
    {
        "length_mode",
        (PyCMethod) Synth_set_player_length_mode,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Mode for loop length automation.\n\n"
        "length_mode(mode)\n"
        "mode  The length mode."},
    {
        "phase_source",
        (PyCMethod) Synth_set_player_phase_source,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the buffer to read phase source samples from.\n\n"
        "phase_source(buffer)\n"
        "buffer  Buffer to modulate the playback position."},
    {
        "speed_mode",
        (PyCMethod) Synth_set_player_speed_mode,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the player's speed mode.\n\n"
        "speed_mode(mode)\n"
        "mode  The speed mode from the auto mode constants."},
    {
        "speed",
        (PyCMethod) Synth_set_player_speed,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the base player speed.\n\n"
        "speed(speed)\n"
        "speed  The base player speed."},
    {
        "speed_source",
        (PyCMethod) Synth_set_player_speed_source,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the source for playback speed.\n\n"
        "speed_source(buffer)\n"
        "buffer  The buffer to modulate the player speed."},
    {
        "run",
        (PyCMethod) Synth_run_player,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Actually run the player.\n\n"
        "run(request)\n"
        "request  The amount of samples the Player should run for."},
    {
        "stop_reason",
        (PyCMethod) Synth_player_stopped_reason,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Determine criteria for why the player stopped.\n\n"
        "stop_reason() -> reason\n"
        "reason  A bitfield of reasons from the reasons constants."},
    {NULL}
};

static PyType_Slot PlayerSlots[] = {
    {Py_tp_doc, "A Player.\n\n"
                "Player(synth, buffer, name)\n"
                "synth   A Synth\n"
                "buffer  A Buffer\n"
                "name    Optional name or None"},
    {Py_tp_new, Player_new},
    {Py_tp_init, (initproc)Player_init},
    {Py_tp_dealloc, (destructor)Player_dealloc},
    {Py_tp_methods, Player_methods},
    {Py_tp_traverse, heap_type_traverse},
    {0, NULL}
};

static PyType_Spec PlayerSpec = {
    .name = "crustygame.Player",
    .basicsize = sizeof(PlayerObject),
    .itemsize = 0,
    .flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .slots = PlayerSlots
};

static PyObject *Filter_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {
    FilterObject *self;

    self = (FilterObject *)type->tp_alloc(type, 0);
    if(self == NULL) {
        return(NULL);
    }
    /* just have it be do-nothing until it's properly initialize */
    self->s = NULL;
    self->inBuffer = NULL;
    self->filterBuffer = NULL;
    self->sliceBuffer = NULL;
    self->outBuffer = NULL;
    self->volBuffer = NULL;
    self->filter = -1;

    return((PyObject *)self);
}

static int Filter_init(FilterObject *self, PyObject *args, PyObject *kwds) {
    BufferObject *buffer = NULL;
    unsigned int size;
    PyObject *name = NULL;
    const char *cname;

    if(self->s != NULL) {
        PyErr_SetString(PyExc_TypeError, "Filter already initialized");
        return(-1);
    }

    /* docs say this init isn't called if the class is instantiated as some
     * other type.  Not sure the consequences there... */
    crustygame_state *state = PyType_GetModuleState(Py_TYPE(self));

    if(!PyArg_ParseTuple(args, "OOIO",
                         &(self->s),
                         &buffer,
                         &size,
                         &name)) {
        self->s = NULL;
        return(-1);
    }
    Py_XINCREF(name);
    Py_XINCREF(self->s);
    Py_XINCREF(buffer);

    if(!PyObject_TypeCheck(self->s, state->SynthType)) {
        PyErr_SetString(PyExc_TypeError, "first argument must be a Synth");
        goto error;
    }
    if(!PyObject_TypeCheck(buffer, state->BufferType)) {
        PyErr_SetString(PyExc_TypeError, "first argument must be a Buffer");
        goto error;
    }
    /* reflect all the buffers which are referenced internally */
    self->inBuffer = buffer;
    Py_XINCREF(self->inBuffer);
    self->filterBuffer = buffer;
    Py_XINCREF(self->filterBuffer);
    self->sliceBuffer = buffer;
    Py_XINCREF(self->sliceBuffer);
    self->outBuffer = self->s->outputBuffers[0];
    Py_XINCREF(self->outBuffer);
    self->volBuffer = buffer;
    Py_XINCREF(self->volBuffer);
    Py_CLEAR(buffer);

    if(name == Py_None) {
        cname = NULL;
    } else {
        cname = PyUnicode_AsUTF8(name);
        if(cname == NULL) {
            goto error;
        }
    }

    self->filter = synth_add_filter(self->s->s, self->inBuffer->buffer, size, cname);
    Py_CLEAR(name);
    if(self->filter < 0) {
        PyErr_SetString(state->CrustyException, "synth_add_filter returned an error");
        goto error;
    }

    return(0);

error:
    Py_XDECREF(name);
    Py_CLEAR(self->volBuffer);
    Py_CLEAR(self->outBuffer);
    Py_CLEAR(self->sliceBuffer);
    Py_CLEAR(self->filterBuffer);
    Py_CLEAR(self->inBuffer);
    Py_CLEAR(buffer);
    Py_CLEAR(self->s);
    return(-1);
}

static void Filter_dealloc(FilterObject *self) {
    if(self->filter >= 0) {
        synth_free_filter(self->s->s, self->filter);
    }
    Py_XDECREF(self->volBuffer);
    Py_XDECREF(self->outBuffer);
    Py_XDECREF(self->sliceBuffer);
    Py_XDECREF(self->filterBuffer);
    Py_XDECREF(self->inBuffer);
    Py_XDECREF(self->s);
    Py_TYPE(self)->tp_free((PyObject *) self);
}

static PyObject *Synth_reset_filter(FilterObject *self,
                                    PyTypeObject *defining_class,
                                    PyObject *const *args,
                                    Py_ssize_t nargs,
                                    PyObject *kwnames) {
    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Buffer is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(synth_reset_filter(self->s->s, self->filter)) {
        PyErr_SetString(state->CrustyException, "synth_player_stopped_reason failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_set_filter_input_buffer(FilterObject *self,
                                               PyTypeObject *defining_class,
                                               PyObject *const *args,
                                               Py_ssize_t nargs,
                                               PyObject *kwnames) {
    BufferObject *buffer;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    if(!PyObject_TypeCheck(args[0], state->BufferType)) {
        PyErr_SetString(PyExc_TypeError, "first argument must be a Buffer");
        return(NULL);
    }
    buffer = (BufferObject *)(args[0]);

    if(synth_set_filter_input_buffer(self->s->s, self->filter, buffer->buffer) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_filter_input_buffer failed");
        return(NULL);
    }
    Py_DECREF(self->inBuffer);
    self->inBuffer = buffer;
    Py_INCREF(self->inBuffer);

    Py_RETURN_NONE;
}

static PyObject *Synth_set_filter_input_buffer_pos(FilterObject *self,
                                                   PyTypeObject *defining_class,
                                                   PyObject *const *args,
                                                   Py_ssize_t nargs,
                                                   PyObject *kwnames) {
    int pos;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    pos = PyLong_AsLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    if(synth_set_filter_input_buffer_pos(self->s->s, self->filter, pos) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_filter_input_buffer_pos failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_set_filter_buffer(FilterObject *self,
                                         PyTypeObject *defining_class,
                                         PyObject *const *args,
                                         Py_ssize_t nargs,
                                         PyObject *kwnames) {
    BufferObject *buffer;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    if(!PyObject_TypeCheck(args[0], state->BufferType)) {
        PyErr_SetString(PyExc_TypeError, "first argument must be a Buffer");
        return(NULL);
    }
    buffer = (BufferObject *)(args[0]);

    if(synth_set_filter_buffer(self->s->s, self->filter, buffer->buffer) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_filter_buffer failed");
        return(NULL);
    }
    Py_DECREF(self->filterBuffer);
    self->filterBuffer = buffer;
    Py_INCREF(self->filterBuffer);

    Py_RETURN_NONE;
}

static PyObject *Synth_set_filter_buffer_start(FilterObject *self,
                                               PyTypeObject *defining_class,
                                               PyObject *const *args,
                                               Py_ssize_t nargs,
                                               PyObject *kwnames) {
    int pos;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    pos = PyLong_AsLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    if(synth_set_filter_buffer_start(self->s->s, self->filter, pos) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_filter_buffer_start failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_set_filter_slices(FilterObject *self,
                                         PyTypeObject *defining_class,
                                         PyObject *const *args,
                                         Py_ssize_t nargs,
                                         PyObject *kwnames) {
    unsigned int slices;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    slices = PyLong_AsUnsignedLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    if(synth_set_filter_slices(self->s->s, self->filter, slices) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_filter_slices failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_set_filter_mode(FilterObject *self,
                                       PyTypeObject *defining_class,
                                       PyObject *const *args,
                                       Py_ssize_t nargs,
                                       PyObject *kwnames) {
    int mode;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    mode = PyLong_AsLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    if(synth_set_filter_mode(self->s->s, self->filter, mode) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_filter_mode failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_set_filter_slice(FilterObject *self,
                                        PyTypeObject *defining_class,
                                        PyObject *const *args,
                                        Py_ssize_t nargs,
                                        PyObject *kwnames) {
    int slice;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    slice = PyLong_AsLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    if(synth_set_filter_slice(self->s->s, self->filter, slice) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_filter_slice failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_set_filter_slice_source(FilterObject *self,
                                               PyTypeObject *defining_class,
                                               PyObject *const *args,
                                               Py_ssize_t nargs,
                                               PyObject *kwnames) {
    BufferObject *buffer;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    if(!PyObject_TypeCheck(args[0], state->BufferType)) {
        PyErr_SetString(PyExc_TypeError, "first argument must be a Buffer");
        return(NULL);
    }
    buffer = (BufferObject *)(args[0]);

    if(synth_set_filter_slice_source(self->s->s, self->filter, buffer->buffer) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_filter_slice_source failed");
        return(NULL);
    }
    Py_DECREF(self->sliceBuffer);
    self->sliceBuffer = buffer;
    Py_INCREF(self->sliceBuffer);

    Py_RETURN_NONE;
}

static PyObject *Synth_set_filter_output_buffer(FilterObject *self,
                                                PyTypeObject *defining_class,
                                                PyObject *const *args,
                                                Py_ssize_t nargs,
                                                PyObject *kwnames) {
    BufferObject *buffer;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    if(!PyObject_TypeCheck(args[0], state->BufferType)) {
        PyErr_SetString(PyExc_TypeError, "first argument must be a Buffer");
        return(NULL);
    }
    buffer = (BufferObject *)(args[0]);

    if(synth_set_filter_output_buffer(self->s->s, self->filter, buffer->buffer) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_filter_output_buffer failed");
        return(NULL);
    }
    Py_DECREF(self->outBuffer);
    self->outBuffer = buffer;
    Py_INCREF(self->outBuffer);

    Py_RETURN_NONE;
}

static PyObject *Synth_set_filter_output_buffer_pos(FilterObject *self,
                                                    PyTypeObject *defining_class,
                                                    PyObject *const *args,
                                                    Py_ssize_t nargs,
                                                    PyObject *kwnames) {
    int pos;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    pos = PyLong_AsLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    if(synth_set_filter_output_buffer_pos(self->s->s, self->filter, pos) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_filter_output_buffer_pos failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_set_filter_output_mode(FilterObject *self,
                                              PyTypeObject *defining_class,
                                              PyObject *const *args,
                                              Py_ssize_t nargs,
                                              PyObject *kwnames) {
    int mode;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    mode = PyLong_AsLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    if(synth_set_filter_output_mode(self->s->s, self->filter, mode) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_filter_output_mode failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_set_filter_volume_mode(FilterObject *self,
                                              PyTypeObject *defining_class,
                                              PyObject *const *args,
                                              Py_ssize_t nargs,
                                              PyObject *kwnames) {
    int mode;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    mode = PyLong_AsLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    if(synth_set_filter_volume_mode(self->s->s, self->filter, mode) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_filter_volume_mode failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_set_filter_volume(FilterObject *self,
                                         PyTypeObject *defining_class,
                                         PyObject *const *args,
                                         Py_ssize_t nargs,
                                         PyObject *kwnames) {
    float volume;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    volume = (float)PyFloat_AsDouble(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    if(synth_set_filter_volume(self->s->s, self->filter, volume) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_filter_volume failed");
        return(NULL);
    }

    Py_RETURN_NONE;
}

static PyObject *Synth_set_filter_volume_source(FilterObject *self,
                                                PyTypeObject *defining_class,
                                                PyObject *const *args,
                                                Py_ssize_t nargs,
                                                PyObject *kwnames) {
    BufferObject *buffer;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    if(!PyObject_TypeCheck(args[0], state->BufferType)) {
        PyErr_SetString(PyExc_TypeError, "first argument must be a Buffer");
        return(NULL);
    }
    buffer = (BufferObject *)(args[0]);

    if(synth_set_filter_volume_source(self->s->s, self->filter, buffer->buffer) < 0) {
        PyErr_SetString(state->CrustyException, "synth_set_filter_volume_source failed");
        return(NULL);
    }
    Py_DECREF(self->volBuffer);
    self->volBuffer = buffer;
    Py_INCREF(self->volBuffer);

    Py_RETURN_NONE;
}

static PyObject *Synth_run_filter(FilterObject *self,
                                  PyTypeObject *defining_class,
                                  PyObject *const *args,
                                  Py_ssize_t nargs,
                                  PyObject *kwnames) {
    unsigned int req;
    int ret;

    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Synth is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    if(nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 1 argument");
        return(NULL);
    }
    req = PyLong_AsUnsignedLong(args[0]);
    if(PyErr_Occurred() != NULL) {
        return(NULL);
    }

    ret = synth_run_filter(self->s->s, self->filter, req);
    if(ret < 0) {
        PyErr_SetString(state->CrustyException, "synth_run_filter failed");
        return(NULL);
    }

    return(PyLong_FromLong(ret));
}

static PyObject *Synth_filter_stopped_reason(FilterObject *self,
                                             PyTypeObject *defining_class,
                                             PyObject *const *args,
                                             Py_ssize_t nargs,
                                             PyObject *kwnames) {
    int ret;
    if(self->s == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "this Buffer is not initialized");
        return(NULL);
    }

    crustygame_state *state = PyType_GetModuleState(defining_class);

    ret = synth_filter_stopped_reason(self->s->s, self->filter);
    if(ret < 0) {
        PyErr_SetString(state->CrustyException, "synth_filter_stopped_reason failed");
        return(NULL);
    }

    return(PyLong_FromLong(ret));
}

static PyMethodDef Filter_methods[] = {
    {
        "reset",
        (PyCMethod) Synth_reset_filter,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Reset the filter accumulation state.\n\n"
        "reset()"},
    {
        "input",
        (PyCMethod) Synth_set_filter_input_buffer,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the buffer to apply a filter to.\n\n"
        "input(buffer)\n"
        "buffer  The buffer the filter should read from."},
    {
        "input_pos",
        (PyCMethod) Synth_set_filter_input_buffer_pos,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the starting position on processing the input buffer\n\n"
        "input_pos(pos)\n"
        "pos  The sample to start reading from."},
    {
        "filter",
        (PyCMethod) Synth_set_filter_buffer,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the buffer containing the filter kernel(s) this filter should use.\n\n"
        "filter(buffer)\n"
        "buffer  The filter containing buffer."},
    {
        "filter_start",
        (PyCMethod) Synth_set_filter_buffer_start,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the position in the buffer where kernel(s) should start to be referenced from.\n\n"
        "filter_start(pos)\n"
        "pos  Start sample of first kernel."},
    {
        "slices",
        (PyCMethod) Synth_set_filter_slices,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the number of consecutive filter kernels starting from the start position which are in the filter buffer.\n\n"
        "slices(num)\n"
        "num  Number of slices."},
    {
        "mode",
        (PyCMethod) Synth_set_filter_mode,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set whether the filter slice is a constant value or whether a buffer should be read to determine which slice should be used per input sample.\n\n"
        "mode(mode)\n"
        "mode  Filter mode from auto constants."},
    {
        "slice",
        (PyCMethod) Synth_set_filter_slice,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the filter slice value to use in constant more or the first slice in slice buffer source mode.\n\n"
        "slice(num)\n"
        "slice  Base filter slice"},
    {
        "slice_source",
        (PyCMethod) Synth_set_filter_slice_source,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Provide the source buffer for slices.\n\n"
        "slice_source(buffer)\n"
        "buffer  Buffer to modulate filter slice."},
    {
        "output",
        (PyCMethod) Synth_set_filter_output_buffer,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the buffer to be output to.\n\n"
        "output(buffer)\n"
        "buffer  Buffer to output to."},
    {
        "output_pos",
        (PyCMethod) Synth_set_filter_output_buffer_pos,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the buffer output position.\n\n"
        "output_pos(pos)\n"
        "pos  Sample to start output from."},
    {
        "output_mode",
        (PyCMethod) Synth_set_filter_output_mode,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the filter's output mode.\n\n"
        "output_mode(mode)\n"
        "mode  Filter output mode from output mode constants."},
    {
        "volume_mode",
        (PyCMethod) Synth_set_filter_volume_mode,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the filter's volume mode.\n\n"
        "volume_mode(mode)\n"
        "mode  Volume mode from auto constants."},
    {
        "volume",
        (PyCMethod) Synth_set_filter_volume,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the filter's volume.\n\n"
        "volume(vol)\n"
        "vol  Filter output volume."},
    {
        "volume_source",
        (PyCMethod) Synth_set_filter_volume_source,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Set the filter's volume source.\n\n"
        "volume_source(buffer)\n"
        "buffer  Buffer to modulate output volume."},
    {
        "run",
        (PyCMethod) Synth_run_filter,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Run the filter for a certain number of samples.\n\n"
        "run(requested)\n"
        "requested  Number of samples to run the filter for."},
    {
        "stop_reason",
        (PyCMethod) Synth_filter_stopped_reason,
        METH_METHOD | METH_FASTCALL | METH_KEYWORDS,
        "Determine criteria for why the filter stopped.\n\n"
        "stop_reason() -> reason\n"
        "reason  Bitfield of reasons from the reasons constants."},
    {NULL}
};

static PyType_Slot FilterSlots[] = {
    {Py_tp_doc, "A Filter.\n\n"
                "Filter(synth, buffer, size, name)\n"
                "synth   A Synth\n"
                "buffer  A Buffer\n"
                "size    The size of the filter\n"
                "name    Optional name or None"},
    {Py_tp_new, Filter_new},
    {Py_tp_init, (initproc)Filter_init},
    {Py_tp_dealloc, (destructor)Filter_dealloc},
    {Py_tp_methods, Filter_methods},
    {Py_tp_traverse, heap_type_traverse},
    {0, NULL}
};

static PyType_Spec FilterSpec = {
    .name = "crustygame.Filter",
    .basicsize = sizeof(FilterObject),
    .itemsize = 0,
    .flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .slots = FilterSlots
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
    state->SynthType = NULL;
    state->BufferType = NULL;
    state->InternalBufferType = NULL;
    state->PlayerType = NULL;
    state->FilterType = NULL;
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

    /* import sdl2 to get the literal pointer types needed for type checks. */
    /* TODO: If this fails, python will segfault on quit. */
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

    /* Make an exception used for problems returned by the library. */
    state->CrustyException = PyErr_NewException("crustygame.CrustyException", NULL, NULL);
    if (PyModule_AddObject(m, "CrustyException", state->CrustyException) < 0) {
        goto error;
    }

    /* heap allocate the new types and store them in the module state */
    /* Can't find any example of anybody using PyTypeFromModuleAndSpec and the
     * documentation says it returns a New reference but by the time the free
     * function is called, the types have a reference count of 0, so it would
     * seem that it doesn't return a reference, at least not in the wya i think
     * that means. */
    state->LayerListType = (PyTypeObject *)PyType_FromModuleAndSpec(m, &LayerListSpec, NULL);
    Py_XINCREF(state->LayerListType);
    if(state->LayerListType == NULL || PyModule_AddObject(m, "LayerList", (PyObject *)state->LayerListType) < 0) {
        goto error;
    }
    state->TilesetType = (PyTypeObject *)PyType_FromModuleAndSpec(m, &TilesetSpec, NULL);
    Py_XINCREF(state->TilesetType);
    if(state->TilesetType == NULL || PyModule_AddObject(m, "Tileset", (PyObject *)state->TilesetType) < 0) {
        goto error;
    }
    state->TilemapType = (PyTypeObject *)PyType_FromModuleAndSpec(m, &TilemapSpec, NULL);
    Py_XINCREF(state->TilemapType);
    if(state->TilemapType == NULL || PyModule_AddObject(m, "Tilemap", (PyObject *)state->TilemapType) < 0) {
        goto error;
    }
    state->LayerType = (PyTypeObject *)PyType_FromModuleAndSpec(m, &LayerSpec, NULL);
    Py_XINCREF(state->LayerType);
    if(state->LayerType == NULL || PyModule_AddObject(m, "Layer", (PyObject *)state->LayerType) < 0) {
        goto error;
    }
    state->SynthType = (PyTypeObject *)PyType_FromModuleAndSpec(m, &SynthSpec, NULL);
    Py_XINCREF(state->SynthType);
    if(state->SynthType == NULL || PyModule_AddObject(m, "Synth", (PyObject *)state->SynthType) < 0) {
        goto error;
    }
    state->BufferType = (PyTypeObject *)PyType_FromModuleAndSpec(m, &BufferSpec, NULL);
    Py_XINCREF(state->BufferType);
    if(state->BufferType == NULL || PyModule_AddObject(m, "Buffer", (PyObject *)state->BufferType) < 0) {
        goto error;
    }
    state->InternalBufferType = (PyTypeObject *)PyType_FromModuleAndSpec(m, &InternalBufferSpec, NULL);
    Py_XINCREF(state->InternalBufferType);
    if(state->InternalBufferType == NULL || PyModule_AddObject(m, "InternalBuffer", (PyObject *)state->InternalBufferType) < 0) {
        goto error;
    }
    state->PlayerType = (PyTypeObject *)PyType_FromModuleAndSpec(m, &PlayerSpec, NULL);
    Py_XINCREF(state->PlayerType);
    if(state->PlayerType == NULL || PyModule_AddObject(m, "Player", (PyObject *)state->PlayerType) < 0) {
        goto error;
    }
    state->FilterType = (PyTypeObject *)PyType_FromModuleAndSpec(m, &FilterSpec, NULL);
    Py_XINCREF(state->FilterType);
    if(state->FilterType == NULL || PyModule_AddObject(m, "Filter", (PyObject *)state->FilterType) < 0) {
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
    if(PyModule_AddIntMacro(m, SYNTH_DEFAULT_FRAGMENT_SIZE) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, SYNTH_TYPE_INVALID) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, SYNTH_TYPE_U8) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, SYNTH_TYPE_S16) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, SYNTH_TYPE_F32) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, SYNTH_TYPE_F64) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, SYNTH_STOPPED) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, SYNTH_ENABLED) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, SYNTH_RUNNING) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, SYNTH_OUTPUT_REPLACE) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, SYNTH_OUTPUT_ADD) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, SYNTH_AUTO_CONSTANT) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, SYNTH_AUTO_SOURCE) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, SYNTH_MODE_ONCE) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, SYNTH_MODE_LOOP) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, SYNTH_MODE_PHASE_SOURCE) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, SYNTH_STOPPED_OUTBUFFER) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, SYNTH_STOPPED_INBUFFER) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, SYNTH_STOPPED_VOLBUFFER) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, SYNTH_STOPPED_SPEEDBUFFER) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, SYNTH_STOPPED_PHASEBUFFER) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, SYNTH_STOPPED_SLICEBUFFER) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, SYNTH_STOPPED_STARTBUFFER) < 0) {
        goto error;
    }
    if(PyModule_AddIntMacro(m, SYNTH_STOPPED_LENGTHBUFFER) < 0) {
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
    Py_CLEAR(state->FilterType);
    Py_CLEAR(state->PlayerType);
    Py_CLEAR(state->InternalBufferType);
    Py_CLEAR(state->BufferType);
    Py_CLEAR(state->SynthType);
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
    Py_XDECREF(state->FilterType);
    Py_XDECREF(state->PlayerType);
    Py_XDECREF(state->InternalBufferType);
    Py_XDECREF(state->BufferType);
    Py_XDECREF(state->SynthType);
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

/* PySDL2's versions of these methods would require unpacking arrays in to full
 * Python lists of SDL_Point or SDL_Rect just to be repacked in to C arrays so
 * just skip all that nonsense and just take buffers directly which are shaped
 * much like arrays of SDL_Point or SDL_Rect and pass them along as-is. */
static PyObject *RenderDrawPoints(PyObject *self,
                                  PyObject *const *args,
                                  Py_ssize_t nargs) {
    Py_buffer bufmem;
    Py_buffer *buf = NULL;
    PyObject *py_renderer = NULL;
    SDL_Renderer *renderer;
    unsigned int len;

    crustygame_state *state = PyModule_GetState(self);

    if(nargs < 2) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 2 argument");
        goto error;
    }

    if(!PyObject_TypeCheck(args[0], state->LP_SDL_Renderer)) {
        PyErr_SetString(PyExc_TypeError, "got something not an SDL_Renderer");
        goto error;
    }
    py_renderer = args[0];
    Py_INCREF(py_renderer);

    renderer = (SDL_Renderer *)get_value_from_lp_object(state, py_renderer);
    if(renderer == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "couldn't get pointer of SDL_Renderer");
        goto error;
    }

    if(PyObject_GetBuffer(args[1], &bufmem, PyBUF_CONTIG_RO) < 0) {
        return(NULL);
    }
    buf = &bufmem;

    if(buf->ndim == 1 && buf->shape[0] >= 4) {
        if(buf->shape[0] * sizeof(int) != (unsigned int)buf->len) {
            PyErr_SetString(PyExc_BufferError, "computed size doesn't match length");
            goto error;
        }
        len = buf->shape[0] / 2;
    } else if (buf->ndim == 2 && buf->shape[1] == 2 && buf->shape[0] >= 2) {
        if(buf->shape[0] * 2 * sizeof(int) != (unsigned int)buf->len) {
            PyErr_SetString(PyExc_BufferError, "computed size doesn't match length");
            goto error;
        }
        len = buf->shape[0];
    } else {
        PyErr_SetString(PyExc_BufferError, "Shape must be either 1-D or 2-D with at least 2 contiugous pairs of values.");
        goto error;
    }

    if(SDL_RenderDrawPoints(renderer, buf->buf, len) < 0) {
        PyErr_SetString(PyExc_RuntimeError, "SDL_RenderDrawPoints returned failure");
        goto error;
    }

    Py_DECREF(py_renderer);
    PyBuffer_Release(buf);
    Py_RETURN_NONE;

error:
    Py_XDECREF(py_renderer);
    if(buf != NULL) {
        PyBuffer_Release(buf);
    }
    return(NULL);
}

static PyObject *RenderDrawLines(PyObject *self,
                                 PyObject *const *args,
                                 Py_ssize_t nargs) {
    Py_buffer bufmem;
    Py_buffer *buf = NULL;
    PyObject *py_renderer = NULL;
    SDL_Renderer *renderer;
    unsigned int len;

    crustygame_state *state = PyModule_GetState(self);

    if(nargs < 2) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 2 argument");
        goto error;
    }

    if(!PyObject_TypeCheck(args[0], state->LP_SDL_Renderer)) {
        PyErr_SetString(PyExc_TypeError, "got something not an SDL_Renderer");
        goto error;
    }
    py_renderer = args[0];
    Py_INCREF(py_renderer);

    renderer = (SDL_Renderer *)get_value_from_lp_object(state, py_renderer);
    if(renderer == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "couldn't get pointer of SDL_Renderer");
        goto error;
    }

    if(PyObject_GetBuffer(args[1], &bufmem, PyBUF_CONTIG_RO) < 0) {
        return(NULL);
    }
    buf = &bufmem;

    if(buf->ndim == 1 && buf->shape[0] >= 4) {
        if(buf->shape[0] * sizeof(int) != (unsigned int)buf->len) {
            PyErr_SetString(PyExc_BufferError, "computed size doesn't match length");
            goto error;
        }
        len = buf->shape[0] / 2;
    } else if (buf->ndim == 2 && buf->shape[1] == 2 && buf->shape[0] >= 2) {
        if(buf->shape[0] * 2 * sizeof(int) != (unsigned int)buf->len) {
            PyErr_SetString(PyExc_BufferError, "computed size doesn't match length");
            goto error;
        }
        len = buf->shape[0];
    } else {
        PyErr_SetString(PyExc_BufferError, "Shape must be either 1-D or 2-D with at least 2 contiugous pairs of values.");
        goto error;
    }

    if(SDL_RenderDrawLines(renderer, buf->buf, len) < 0) {
        PyErr_SetString(PyExc_RuntimeError, "SDL_RenderDrawPoints returned failure");
        goto error;
    }

    Py_DECREF(py_renderer);
    PyBuffer_Release(buf);
    Py_RETURN_NONE;

error:
    Py_XDECREF(py_renderer);
    if(buf != NULL) {
        PyBuffer_Release(buf);
    }
    return(NULL);
}

static PyObject *RenderDrawRects(PyObject *self,
                                 PyObject *const *args,
                                 Py_ssize_t nargs) {
    Py_buffer bufmem;
    Py_buffer *buf = NULL;
    PyObject *py_renderer = NULL;
    SDL_Renderer *renderer;
    unsigned int len;

    crustygame_state *state = PyModule_GetState(self);

    if(nargs < 2) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 2 argument");
        goto error;
    }

    if(!PyObject_TypeCheck(args[0], state->LP_SDL_Renderer)) {
        PyErr_SetString(PyExc_TypeError, "got something not an SDL_Renderer");
        goto error;
    }
    py_renderer = args[0];
    Py_INCREF(py_renderer);

    renderer = (SDL_Renderer *)get_value_from_lp_object(state, py_renderer);
    if(renderer == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "couldn't get pointer of SDL_Renderer");
        goto error;
    }

    if(PyObject_GetBuffer(args[1], &bufmem, PyBUF_CONTIG_RO) < 0) {
        return(NULL);
    }
    buf = &bufmem;

    if(buf->ndim == 1 && buf->shape[0] >= 4) {
        if(buf->shape[0] * sizeof(int) != (unsigned int)buf->len) {
            PyErr_SetString(PyExc_BufferError, "computed size doesn't match length");
            goto error;
        }
        len = buf->shape[0] / 4;
    } else if (buf->ndim == 2 && buf->shape[1] == 4 && buf->shape[0] >= 1) {
        if(buf->shape[0] * 2 * sizeof(int) != (unsigned int)buf->len) {
            PyErr_SetString(PyExc_BufferError, "computed size doesn't match length");
            goto error;
        }
        len = buf->shape[0];
    } else {
        PyErr_SetString(PyExc_BufferError, "Shape must be either 1-D or 2-D with at least 2 contiugous pairs of values.");
        goto error;
    }

    if(SDL_RenderDrawRects(renderer, buf->buf, len) < 0) {
        PyErr_SetString(PyExc_RuntimeError, "SDL_RenderDrawRects returned failure");
        goto error;
    }

    Py_DECREF(py_renderer);
    PyBuffer_Release(buf);
    Py_RETURN_NONE;

error:
    Py_XDECREF(py_renderer);
    if(buf != NULL) {
        PyBuffer_Release(buf);
    }
    return(NULL);
}

static PyObject *RenderDrawPointsF(PyObject *self,
                                   PyObject *const *args,
                                   Py_ssize_t nargs) {
    Py_buffer bufmem;
    Py_buffer *buf = NULL;
    PyObject *py_renderer = NULL;
    SDL_Renderer *renderer;
    unsigned int len;

    crustygame_state *state = PyModule_GetState(self);

    if(nargs < 2) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 2 argument");
        goto error;
    }

    if(!PyObject_TypeCheck(args[0], state->LP_SDL_Renderer)) {
        PyErr_SetString(PyExc_TypeError, "got something not an SDL_Renderer");
        goto error;
    }
    py_renderer = args[0];
    Py_INCREF(py_renderer);

    renderer = (SDL_Renderer *)get_value_from_lp_object(state, py_renderer);
    if(renderer == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "couldn't get pointer of SDL_Renderer");
        goto error;
    }

    if(PyObject_GetBuffer(args[1], &bufmem, PyBUF_CONTIG_RO) < 0) {
        return(NULL);
    }
    buf = &bufmem;

    if(buf->ndim == 1 && buf->shape[0] >= 4) {
        if(buf->shape[0] * sizeof(float) != (unsigned int)buf->len) {
            PyErr_SetString(PyExc_BufferError, "computed size doesn't match length");
            goto error;
        }
        len = buf->shape[0] / 2;
    } else if (buf->ndim == 2 && buf->shape[1] == 2 && buf->shape[0] >= 2) {
        if(buf->shape[0] * 2 * sizeof(float) != (unsigned int)buf->len) {
            PyErr_SetString(PyExc_BufferError, "computed size doesn't match length");
            goto error;
        }
        len = buf->shape[0];
    } else {
        PyErr_SetString(PyExc_BufferError, "Shape must be either 1-D or 2-D with at least 2 contiugous pairs of values.");
        goto error;
    }

    if(SDL_RenderDrawPointsF(renderer, buf->buf, len) < 0) {
        PyErr_SetString(PyExc_RuntimeError, "SDL_RenderDrawPointsF returned failure");
        goto error;
    }

    Py_DECREF(py_renderer);
    PyBuffer_Release(buf);
    Py_RETURN_NONE;

error:
    Py_XDECREF(py_renderer);
    if(buf != NULL) {
        PyBuffer_Release(buf);
    }
    return(NULL);
}

static PyObject *RenderDrawLinesF(PyObject *self,
                                  PyObject *const *args,
                                  Py_ssize_t nargs) {
    Py_buffer bufmem;
    Py_buffer *buf = NULL;
    PyObject *py_renderer = NULL;
    SDL_Renderer *renderer;
    unsigned int len;

    crustygame_state *state = PyModule_GetState(self);

    if(nargs < 2) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 2 argument");
        goto error;
    }

    if(!PyObject_TypeCheck(args[0], state->LP_SDL_Renderer)) {
        PyErr_SetString(PyExc_TypeError, "got something not an SDL_Renderer");
        goto error;
    }
    py_renderer = args[0];
    Py_INCREF(py_renderer);

    renderer = (SDL_Renderer *)get_value_from_lp_object(state, py_renderer);
    if(renderer == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "couldn't get pointer of SDL_Renderer");
        goto error;
    }

    if(PyObject_GetBuffer(args[1], &bufmem, PyBUF_CONTIG_RO) < 0) {
        return(NULL);
    }
    buf = &bufmem;

    if(buf->ndim == 1 && buf->shape[0] >= 4) {
        if(buf->shape[0] * sizeof(float) != (unsigned int)buf->len) {
            PyErr_SetString(PyExc_BufferError, "computed size doesn't match length");
            goto error;
        }
        len = buf->shape[0] / 2;
    } else if (buf->ndim == 2 && buf->shape[1] == 2 && buf->shape[0] >= 2) {
        if(buf->shape[0] * 2 * sizeof(float) != (unsigned int)buf->len) {
            PyErr_SetString(PyExc_BufferError, "computed size doesn't match length");
            goto error;
        }
        len = buf->shape[0];
    } else {
        PyErr_SetString(PyExc_BufferError, "Shape must be either 1-D or 2-D with at least 2 contiugous pairs of values.");
        goto error;
    }

    if(SDL_RenderDrawLinesF(renderer, buf->buf, len) < 0) {
        PyErr_SetString(PyExc_RuntimeError, "SDL_RenderDrawLinesF returned failure");
        goto error;
    }

    Py_DECREF(py_renderer);
    PyBuffer_Release(buf);
    Py_RETURN_NONE;

error:
    Py_XDECREF(py_renderer);
    if(buf != NULL) {
        PyBuffer_Release(buf);
    }
    return(NULL);
}

static PyObject *RenderDrawRectsF(PyObject *self,
                                  PyObject *const *args,
                                  Py_ssize_t nargs) {
    Py_buffer bufmem;
    Py_buffer *buf = NULL;
    PyObject *py_renderer = NULL;
    SDL_Renderer *renderer;
    unsigned int len;

    crustygame_state *state = PyModule_GetState(self);

    if(nargs < 2) {
        PyErr_SetString(PyExc_TypeError, "function needs at least 2 argument");
        goto error;
    }

    if(!PyObject_TypeCheck(args[0], state->LP_SDL_Renderer)) {
        PyErr_SetString(PyExc_TypeError, "got something not an SDL_Renderer");
        goto error;
    }
    py_renderer = args[0];
    Py_INCREF(py_renderer);

    renderer = (SDL_Renderer *)get_value_from_lp_object(state, py_renderer);
    if(renderer == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "couldn't get pointer of SDL_Renderer");
        goto error;
    }

    if(PyObject_GetBuffer(args[1], &bufmem, PyBUF_CONTIG_RO) < 0) {
        return(NULL);
    }
    buf = &bufmem;

    if(buf->ndim == 1 && buf->shape[0] >= 4) {
        if(buf->shape[0] * sizeof(float) != (unsigned int)buf->len) {
            PyErr_SetString(PyExc_BufferError, "computed size doesn't match length");
            goto error;
        }
        len = buf->shape[0] / 4;
    } else if (buf->ndim == 2 && buf->shape[1] == 4 && buf->shape[0] >= 1) {
        if(buf->shape[0] * 2 * sizeof(float) != (unsigned int)buf->len) {
            PyErr_SetString(PyExc_BufferError, "computed size doesn't match length");
            goto error;
        }
        len = buf->shape[0];
    } else {
        PyErr_SetString(PyExc_BufferError, "Shape must be either 1-D or 2-D with at least 2 contiugous pairs of values.");
        goto error;
    }

    if(SDL_RenderDrawRectsF(renderer, buf->buf, len) < 0) {
        PyErr_SetString(PyExc_RuntimeError, "SDL_RenderDrawRectsF returned failure");
        goto error;
    }

    Py_DECREF(py_renderer);
    PyBuffer_Release(buf);
    Py_RETURN_NONE;

error:
    Py_XDECREF(py_renderer);
    if(buf != NULL) {
        PyBuffer_Release(buf);
    }
    return(NULL);
}

static struct PyMethodDef crustygamefuncs[] = {
    {"SDL_RenderDrawPoints",
        (_PyCFunctionFast)RenderDrawPoints,  METH_FASTCALL,
        "Wrapper for SDL_RenderDrawPoints that accepts PyBuffers.\n\n"
        "SDL_RenderDrawPoints(renderer, array)\n"
        "renderer  The SDL_Renderer.\n"
        "array     A PyBuffer either as Nx2 array or even number 1D array of 32 bit integer X-Y pairs."},
    {"SDL_RenderDrawLines",
        (_PyCFunctionFast)RenderDrawLines,   METH_FASTCALL,
        "Wrapper for SDL_RenderDrawLines that accepts PyBuffers.\n\n"
        "SDL_RenderDrawPoints(renderer, array)\n"
        "renderer  The SDL_Renderer.\n"
        "array     A PyBuffer either as Nx2 array or even number 1D array of 32 bit integer X-Y pairs."},
    {"SDL_RenderDrawRects",
        (_PyCFunctionFast)RenderDrawRects,   METH_FASTCALL,
        "Wrapper for SDL_RenderDrawRects that accepts PyBuffers.\n\n"
        "SDL_RenderDrawPoints(renderer, array)\n"
        "renderer  The SDL_Renderer.\n"
        "array     A PyBuffer either as Nx4 array or multiple of four 1D array of 32 bit integer X, Y, width, height values."},
    {"SDL_RenderDrawPointsF",
        (_PyCFunctionFast)RenderDrawPointsF, METH_FASTCALL,
        "Wrapper for SDL_RenderDrawPointsF that accepts PyBuffers.\n\n"
        "SDL_RenderDrawPoints(renderer, array)\n"
        "renderer  The SDL_Renderer.\n"
        "array     A PyBuffer either as Nx2 array or even number 1D array of 32 bit float X-Y pairs."},
    {"SDL_RenderDrawLinesF",
        (_PyCFunctionFast)RenderDrawLinesF,  METH_FASTCALL,
        "Wrapper for SDL_RenderDrawLinesF that accepts PyBuffers.\n\n"
        "SDL_RenderDrawPoints(renderer, array)\n"
        "renderer  The SDL_Renderer.\n"
        "array     A PyBuffer either as Nx2 array or even number 1D array of 32 bit float X-Y pairs."},
    {"SDL_RenderDrawRectsF",
        (_PyCFunctionFast)RenderDrawRectsF,  METH_FASTCALL,
        "Wrapper for SDL_RenderDrawRectsF that accepts PyBuffers.\n\n"
        "SDL_RenderDrawPoints(renderer, array)\n"
        "renderer  The SDL_Renderer.\n"
        "array     A PyBuffer either as Nx4 array or multiple of four 1D array of 32 bit float X, Y, width, height values."},
    {NULL}
};

static struct PyModuleDef crustygamemodule = {
    PyModuleDef_HEAD_INIT,
    .m_name = "crustygame",
    .m_doc = NULL,
    .m_size = sizeof(crustygame_state),
    .m_methods = crustygamefuncs,
    .m_slots = crustygamemodule_slots,
    .m_free = (freefunc)crustygame_free
};

PyMODINIT_FUNC PyInit_crustygame(void) {
    return(PyModuleDef_Init(&crustygamemodule));
}
