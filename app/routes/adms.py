"""
ZKTeco ADMS / Push endpoints (iclock protocol).

Separate from Pull sync (/api/fingerprint/sync). Devices POST attendance
to /iclock/cdata; responses are plain-text OK as required by the firmware.
"""

from flask import Blueprint, current_app, request, Response
from app.routes.attendance import ingest_fingerprint_records

adms_bp = Blueprint('adms', __name__)


def _plain_ok(extra: str = '') -> Response:
    body = 'OK' if not extra else f'OK\n{extra}'
    return Response(body, status=200, mimetype='text/plain')


def _adms_enabled() -> bool:
    return bool(current_app.config.get('ADMS_ENABLED', True))


def _serial_allowed(sn: str) -> bool:
    allowed = current_app.config.get('ADMS_ALLOWED_SERIALS') or []
    if not allowed:
        return True
    return (sn or '').strip() in {str(s).strip() for s in allowed}


def _parse_attlog(body: str, device_name: str):
    """
    ATTLOG lines: PIN \\t YYYY-MM-DD HH:MM:SS \\t status \\t verify \\t ...
    """
    records = []
    for raw_line in (body or '').splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split('\t')
        if len(parts) < 2:
            continue
        pin = parts[0].strip()
        ts = parts[1].strip()
        if not pin or not ts:
            continue
        status = 0
        punch = 0
        if len(parts) > 2:
            try:
                status = int(parts[2])
            except (TypeError, ValueError):
                status = 0
        if len(parts) > 3:
            try:
                punch = int(parts[3])
            except (TypeError, ValueError):
                punch = 0
        records.append({
            'fingerprint_id': pin,
            'timestamp': ts,
            'status': status,
            'punch': punch,
            'device_name': device_name or 'ADMS',
        })
    return records


@adms_bp.route('/iclock/cdata', methods=['GET', 'POST'])
def iclock_cdata():
    if not _adms_enabled():
        return Response('ERROR: ADMS disabled', status=403, mimetype='text/plain')

    sn = (request.args.get('SN') or request.args.get('sn') or '').strip()
    if not _serial_allowed(sn):
        current_app.logger.warning('ADMS rejected SN=%s', sn)
        return Response('ERROR: SN not allowed', status=403, mimetype='text/plain')

    table = (request.args.get('table') or '').strip().upper()

    # Handshake / options request from device
    if request.method == 'GET':
        # Minimal options block some firmwares expect after options=all
        if 'options' in request.args:
            opts = (
                f"GET OPTION FROM: {sn}\n"
                "ATTLOGStamp=None\n"
                "OPERLOGStamp=None\n"
                "ATTPHOTOStamp=None\n"
                "ErrorDelay=30\n"
                "Delay=10\n"
                "TransTimes=00:00;14:00\n"
                "TransInterval=1\n"
                "TransFlag=1111000000\n"
                "TimeZone=3\n"
                "Realtime=1\n"
                "Encrypt=0\n"
            )
            return Response(opts, status=200, mimetype='text/plain')
        return _plain_ok()

    # POST: attendance / oper logs
    raw = request.get_data(as_text=True) or ''
    current_app.logger.info(
        'ADMS cdata SN=%s table=%s bytes=%s', sn, table or '-', len(raw)
    )

    # ATTLOG explicitly, or non-empty body when table omitted
    if table == 'ATTLOG' or (not table and raw.strip()):
        device_name = sn or 'ADMS'
        records = _parse_attlog(raw, device_name)
        if not records:
            return _plain_ok()
        payload, code = ingest_fingerprint_records(records)
        results = payload.get('results') or {}
        current_app.logger.info(
            'ADMS ATTLOG SN=%s ingested=%s status=%s success=%s updated=%s failed=%s',
            sn,
            len(records),
            payload.get('status'),
            results.get('success'),
            results.get('updated'),
            results.get('failed'),
        )
        # Device protocol still expects OK even if some PINs are unknown,
        # otherwise it may retry forever. Log failures server-side.
        if code >= 500:
            return Response('ERROR', status=500, mimetype='text/plain')
        return _plain_ok()

    # OPERLOG / USERINFO / etc. — acknowledge without processing for now
    return _plain_ok()


@adms_bp.route('/iclock/getrequest', methods=['GET', 'POST'])
def iclock_getrequest():
    if not _adms_enabled():
        return Response('ERROR: ADMS disabled', status=403, mimetype='text/plain')

    sn = (request.args.get('SN') or request.args.get('sn') or '').strip()
    if not _serial_allowed(sn):
        current_app.logger.warning('ADMS getrequest rejected SN=%s', sn)
        return Response('ERROR: SN not allowed', status=403, mimetype='text/plain')

    current_app.logger.debug('ADMS getrequest SN=%s', sn)
    return _plain_ok()


@adms_bp.route('/iclock/devicecmd', methods=['GET', 'POST'])
def iclock_devicecmd():
    if not _adms_enabled():
        return Response('ERROR: ADMS disabled', status=403, mimetype='text/plain')
    return _plain_ok()
