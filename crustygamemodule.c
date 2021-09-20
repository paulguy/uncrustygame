#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "tilemap.h"

static PyObject *CrustyException;

typedef struct {
    PyObject_HEAD
    LayerList *ll;
    PyObject *log_cb;
    PyObject *log_priv;
    PyObject *renderer;
} LayerListObject;

static void log_cb_adapter(const char *str, LayerListObject *self) {
    PyObject *arglist;
    PyObject *result;

    arglist = Py_BuildValue("sO", str, self->log_priv);
    result = PyObject_CallObject(self->log_cb, arglist);
    Py_DECREF(arglist);
    /* don't check the result because this is called by C code anyway and it
     * is void */
    Py_DECREF(result);
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
    if(!PyArg_ParseTuple(args, "OIOO", &renderer, &format, &log_cb, &log_priv)) {
        return(-1);
    }

    if(self->ll != NULL) {
        PyErr_SetString(PyExc_TypeError, "LayerList already initialized");
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
        PyErr_SetString(CrustyException, "layerlist_new returned an error");
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

static PyTypeObject LayerListType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "crustygame.LayerList",
    .tp_doc = "LayerList objects",
    .tp_basicsize = sizeof(LayerListObject),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .tp_new = LayerList_new,
    .tp_init = (initproc) LayerList_init,
    .tp_dealloc = (destructor) LayerList_dealloc,
/*    .tp_methods = LayerList_methods */
};

static struct PyModuleDef crustygamemodule = {
    PyModuleDef_HEAD_INIT,
    .m_name = "crustygame",
    .m_doc = NULL,
    .m_size = -1
};

PyMODINIT_FUNC
PyInit_crustygame(void) {
    PyObject *m;

    if(PyType_Ready(&LayerListType) < 0) {
        return(NULL);
    }

    m = PyModule_Create(&crustygamemodule);
    if (m == NULL) {
        return NULL;
    }

    CrustyException = PyErr_NewException("crustygame.CrustyException", NULL, NULL);
    Py_XINCREF(CrustyException);
    if (PyModule_AddObject(m, "CrustyException", CrustyException) < 0) {
        Py_XDECREF(CrustyException);
        Py_CLEAR(CrustyException);
        Py_DECREF(m);
        return NULL;
    }

    Py_INCREF(&LayerListType);
    if(PyModule_AddObject(m, "LayerList", (PyObject *) &LayerListType) < 0) {
        Py_DECREF(&LayerListType);
        Py_DECREF(CrustyException);
        Py_CLEAR(CrustyException);
        Py_DECREF(m);
        return(NULL);
    }

    return m;
}
