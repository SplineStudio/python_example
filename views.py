from django.views.decorators.csrf import csrf_exempt

from services.response import JsonResponse
from services.decorator_valid_body import validate_body
from login.models import (Machines, Operator, Machines_and_Operators, MachineConditions, OPERATOR, MONITORING,
                          SUPER_ADMIN_ID)
from login.models import Machines_and_Operators as mongo_m_n_o
from websocket.consumers import send


@csrf_exempt
@validate_body(('token', 'qr'))
def select_machines(request):
    if not request.user.get_permission(OPERATOR):
        return JsonResponse(error='wrong permission')
    cnc = Machines.objects.filter(uid=request.body.get('qr')).first()
    if cnc is None:
        return JsonResponse(error='wrong qr code to cnc')
    status = Machines_and_Operators.objects.filter(machine_id=cnc.id)
    states = MachineConditions.objects.all().values('id', 'title', 'color')

    if status.first() is None:
        Machines_and_Operators.objects.create(operator_id=request.user.id, machine_id=cnc.id)
    elif status.first().operator_id == request.user.id:
        pass
    else:
        poor_id = status.first().operator_id
        body = status.values()[0]
        body['status'] = 'was reconnect to another operator'
        mongo_m_n_o.objects.create(**body)
        cnc = Machines.objects.filter(id=status.first().machine_id).first()
        Machines_and_Operators.objects.filter(id=status.first().id).delete()
        cncs = Operator.objects.filter(id=poor_id).first().cnc.all()
        send(poor_id, {'cnc_name': cnc.name,
                       'cnc_id': cnc.id,
                       'user_name': request.user.username,
                       "data": list(cncs.values('id', 'name', 'state_id')),
                       'states': list(states)})
        Machines_and_Operators.objects.create(operator_id=request.user.id, machine_id=cnc.id)
    cncs = Operator.objects.filter(id=request.user.id).first().cnc.all()
    send(request.user.id, {'data': list(cncs.all().values('id', 'name', 'state_id')), 'states': list(states)})
    return JsonResponse({'data': list(request.user.cnc.all().values('id', 'name', 'state_id')), 'states': list(states)})


@csrf_exempt
@validate_body(('token', 'cnc_id'))
def cnc_logout(request):
    if not request.user.get_permission(OPERATOR):
        return JsonResponse(error='wrong permission')
    cnc = Machines.objects.filter(id=request.body.get('cnc_id')).first()
    if cnc is None:
        return JsonResponse(error='wrong cnc_id')
    status = Machines_and_Operators.objects.filter(machine_id=cnc.id)
    if status.count() == 0 and status.first().operator_id != request.user.id:
        return JsonResponse(error='cnc did not connect ot user')
    else:
        body = status.values()[0]
        body['status'] = 'user was logout from cnc'
        mongo_m_n_o.objects.create(**body)
        Machines_and_Operators.objects.filter(id=status.first().id).delete()
    return JsonResponse()


@csrf_exempt
@validate_body(('id', ))
def send_socket(request):
    id = request.body.get('id')
    link = Machines_and_Operators.objects.filter(machine_id=id).first()
    states = MachineConditions.objects.all().values('id', 'title', 'color')
    print(link)
    if link is not None:
        op = Operator.objects.filter(id=link.operator_id).first()
        send(link.operator_id, {'data': list(op.cnc.all().values('id', 'name', 'state_id')), 'states': list(states)})
    cnc = Machines.objects.all().values('id', 'name', 'serial_number', 'state_id', 'change_state')
    for cnc_item in cnc:
        cnc_item['change_state'] = str(cnc_item['change_state'])
    for monitor in Operator.objects.filter(group=MONITORING):
        send(monitor.id, {'data': list(cnc), 'states': list(states)})
    send(SUPER_ADMIN_ID, {'data': list(cnc), 'states': list(states)})
    return JsonResponse()
