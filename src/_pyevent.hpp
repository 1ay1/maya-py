// _pyevent.hpp — the single PyEvent type shared across the extension's TUs.
//
// pybind11 registers a C++ type's Python class ONCE. If two TUs each define
// their own struct PyEvent (even with identical layout) they are DISTINCT C++
// types to pybind — a value boxed by one TU can't be cast by the other, and
// event predicates silently fail. So the type lives here and every TU that
// needs to construct or accept a Python Event includes this header.

#pragma once
#include <maya/maya.hpp>

struct PyEvent {
    maya::Event ev;
};
