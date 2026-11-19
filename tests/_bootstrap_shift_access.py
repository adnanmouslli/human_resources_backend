"""تحميل shift_access_service مع stubs خفيفة."""
from __future__ import annotations

import importlib.util
import os
import sys
import types
from unittest.mock import MagicMock

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SERVICE_PATH = os.path.join(_ROOT, 'app', 'services', 'shift_access_service.py')
_MODULE_NAME = 'app.services.shift_access_service'


def load_shift_access_service():
    if _MODULE_NAME in sys.modules and getattr(sys.modules[_MODULE_NAME], '_booted', False):
        # أعد التحميل لأن المنطق تغيّر أثناء التطوير
        pass

    app_mod = types.ModuleType('app')
    app_mod.db = MagicMock()

    models_mod = types.ModuleType('app.models')
    models_mod.__path__ = []
    employee_mod = types.ModuleType('app.models.employee')
    attendance_mod = types.ModuleType('app.models.attendance')

    class Employee:
        pass

    class Attendance:
        query = MagicMock()
        empId = MagicMock()
        createdAt = MagicMock()
        checkInTime = MagicMock()
        checkOutTime = MagicMock()
        id = MagicMock()

    employee_mod.Employee = Employee
    attendance_mod.Attendance = Attendance

    services_mod = types.ModuleType('app.services')
    services_mod.__path__ = [os.path.join(_ROOT, 'app', 'services')]

    for key in list(sys.modules):
        if key == 'app' or key.startswith('app.'):
            del sys.modules[key]

    sys.modules['app'] = app_mod
    sys.modules['app.models'] = models_mod
    sys.modules['app.models.employee'] = employee_mod
    sys.modules['app.models.attendance'] = attendance_mod
    sys.modules['app.services'] = services_mod

    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _SERVICE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module._booted = True
    return module
