"""
تهيئة stubs وتحميل advance_limit_service بدون تشغيل app.services.__init__.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import types
from unittest.mock import MagicMock

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SERVICE_PATH = os.path.join(_ROOT, 'app', 'services', 'advance_limit_service.py')
_MODULE_NAME = 'app.services.advance_limit_service'


def load_advance_limit_service():
    if _MODULE_NAME in sys.modules and getattr(sys.modules[_MODULE_NAME], '_booted', False):
        return sys.modules[_MODULE_NAME]

    # stubs قبل exec_module
    app_mod = types.ModuleType('app')
    app_mod._advance_limit_stub = True
    app_mod.db = MagicMock()
    app_mod.db.func = MagicMock()
    app_mod.db.session = MagicMock()

    models_mod = types.ModuleType('app.models')
    models_mod.__path__ = []
    advance_mod = types.ModuleType('app.models.advance')
    transaction_mod = types.ModuleType('app.models.transaction')

    class Advance:
        amount = MagicMock(name='Advance.amount')
        employee_id = MagicMock(name='Advance.employee_id')
        date = MagicMock(name='Advance.date')

    class Transaction:
        query = MagicMock(name='Transaction.query')
        employee_id = MagicMock(name='Transaction.employee_id')
        transaction_type = MagicMock(name='Transaction.transaction_type')
        status = MagicMock(name='Transaction.status')
        id = MagicMock(name='Transaction.id')

    advance_mod.Advance = Advance
    transaction_mod.Transaction = Transaction

    services_mod = types.ModuleType('app.services')
    services_mod.__path__ = [os.path.join(_ROOT, 'app', 'services')]

    for key in list(sys.modules):
        if key == 'app' or key.startswith('app.'):
            # أبقِ فقط إن كان stub سابق لنفس الغرض
            if key == _MODULE_NAME:
                continue
            del sys.modules[key]

    sys.modules['app'] = app_mod
    sys.modules['app.models'] = models_mod
    sys.modules['app.models.advance'] = advance_mod
    sys.modules['app.models.transaction'] = transaction_mod
    sys.modules['app.services'] = services_mod

    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _SERVICE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module._booted = True
    return module
