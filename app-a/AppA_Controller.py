# AppA_Controller.py
# Pythonista 3 / iPhone
#
# App A:
# 1. Tast inn en valgfri 4-sifret kode.
# 2. App B må ha nøyaktig samme kode.
# 3. Trykk "Finn App B".
# 4. Når App B finnes, kobler App A til og sender koden.
# 5. Hvis kodene matcher, kan App A sende søk.

import json
import re
import ui

from objc_util import (
    ObjCClass, ObjCInstance, NSObject, create_objc_class,
    load_framework, ns, on_main_thread
)

load_framework('CoreBluetooth')

CBCentralManager = ObjCClass('CBCentralManager')
CBUUID = ObjCClass('CBUUID')

SERVICE_UUID = 'F19A1000-2D5B-4B65-9B70-8CF8F0A01111'
COMMAND_UUID = 'F19A1001-2D5B-4B65-9B70-8CF8F0A01111'
STATUS_UUID = 'F19A1002-2D5B-4B65-9B70-8CF8F0A01111'

CB_MANAGER_STATE_POWERED_ON = 5
CB_CHARACTERISTIC_WRITE_WITH_RESPONSE = 0

class State:
    code = None
    manager = None
    delegate = None
    peripheral = None
    command_char = None
    status_char = None
    view = None

state = State()


@on_main_thread
def set_status(text):
    print(text)
    if state.view:
        state.view.status.text = text


def send_json(obj):
    if not state.peripheral or not state.command_char:
        set_status('Ikke koblet til App B')
        return

    payload = json.dumps(obj).encode('utf-8')
    data = ObjCClass('NSData').dataWithBytes_length_(payload, len(payload))

    state.peripheral.writeValue_forCharacteristic_type_(
        data,
        state.command_char,
        CB_CHARACTERISTIC_WRITE_WITH_RESPONSE
    )


def centralManagerDidUpdateState_(_self, _cmd, manager_ptr):
    manager = ObjCInstance(manager_ptr)

    if int(manager.state()) == CB_MANAGER_STATE_POWERED_ON:
        set_status('Bluetooth klar – søker etter App B…')
        service = CBUUID.UUIDWithString_(SERVICE_UUID)
        manager.scanForPeripheralsWithServices_options_([service], None)
    else:
        set_status('Bluetooth er ikke klar')


def centralManager_didDiscoverPeripheral_advertisementData_RSSI_(
    _self, _cmd, manager_ptr, peripheral_ptr, adv_ptr, rssi_ptr
):
    manager = ObjCInstance(manager_ptr)
    peripheral = ObjCInstance(peripheral_ptr)

    state.peripheral = peripheral

    manager.stopScan()
    set_status('Fant App B – kobler til…')
    manager.connectPeripheral_options_(peripheral, None)


def centralManager_didConnectPeripheral_(_self, _cmd, manager_ptr, peripheral_ptr):
    peripheral = ObjCInstance(peripheral_ptr)
    state.peripheral = peripheral
    peripheral.setDelegate_(state.delegate)

    set_status('Bluetooth koblet. Finner tjenesten…')
    peripheral.discoverServices_([CBUUID.UUIDWithString_(SERVICE_UUID)])


def peripheral_didDiscoverServices_(_self, _cmd, peripheral_ptr, error_ptr):
    peripheral = ObjCInstance(peripheral_ptr)

    if error_ptr:
        set_status('Feil ved søk etter tjeneste')
        return

    for service in peripheral.services():
        peripheral.discoverCharacteristics_forService_(
            [
                CBUUID.UUIDWithString_(COMMAND_UUID),
                CBUUID.UUIDWithString_(STATUS_UUID)
            ],
            service
        )


def peripheral_didDiscoverCharacteristicsForService_error_(
    _self, _cmd, peripheral_ptr, service_ptr, error_ptr
):
    peripheral = ObjCInstance(peripheral_ptr)
    service = ObjCInstance(service_ptr)

    if error_ptr:
        set_status('Kunne ikke finne Bluetooth-funksjonene')
        return

    for ch in service.characteristics():
        uuid = str(ch.UUID().UUIDString()).upper()

        if uuid == COMMAND_UUID.upper():
            state.command_char = ch

        elif uuid == STATUS_UUID.upper():
            state.status_char = ch
            try:
                peripheral.setNotifyValue_forCharacteristic_(True, ch)
            except Exception:
                pass

    if state.command_char:
        set_status('Sender 4-sifret kode…')
        send_json({'type': 'pair', 'code': state.code})


def peripheral_didWriteValueForCharacteristic_error_(
    _self, _cmd, peripheral_ptr, characteristic_ptr, error_ptr
):
    if error_ptr:
        set_status('Kunne ikke sende melding')
    else:
        if state.command_char:
            set_status('Kode sendt. Hvis kodene er like er dere koblet.')


Delegate = create_objc_class(
    'AppACentralDelegate',
    NSObject,
    methods=[
        centralManagerDidUpdateState_,
        centralManager_didDiscoverPeripheral_advertisementData_RSSI_,
        centralManager_didConnectPeripheral_,
        peripheral_didDiscoverServices_,
        peripheral_didDiscoverCharacteristicsForService_error_,
        peripheral_didWriteValueForCharacteristic_error_,
    ],
    protocols=['CBCentralManagerDelegate', 'CBPeripheralDelegate']
)


class MainView(ui.View):
    def __init__(self):
        self.name = 'App A'
        self.background_color = 'white'

        title = ui.Label(frame=(20, 35, 340, 40))
        title.text = 'App A'
        title.font = ('<System-Bold>', 28)
        self.add_subview(title)

        info = ui.Label(frame=(20, 90, 340, 60))
        info.text = 'Tast inn samme 4-sifrede kode som på App B.'
        info.number_of_lines = 0
        self.add_subview(info)

        self.code = ui.TextField(frame=(20, 165, 220, 48))
        self.code.placeholder = '4-sifret kode'
        self.code.keyboard_type = ui.KEYBOARD_NUMBER_PAD
        self.code.font = ('<System>', 22)
        self.add_subview(self.code)

        connect = ui.Button(frame=(20, 230, 220, 48))
        connect.title = 'Finn App B'
        connect.action = self.connect
        self.add_subview(connect)

        self.search = ui.TextField(frame=(20, 300, 320, 44))
        self.search.placeholder = 'Hva vil du søke etter?'
        self.add_subview(self.search)

        search_btn = ui.Button(frame=(20, 360, 220, 48))
        search_btn.title = 'Søk på App B'
        search_btn.action = self.send_search
        self.add_subview(search_btn)

        self.status = ui.Label(frame=(20, 430, 340, 100))
        self.status.number_of_lines = 0
        self.status.text = 'Ikke koblet'
        self.add_subview(self.status)

    def connect(self, sender):
        code = self.code.text.strip()

        if not re.fullmatch(r'\d{4}', code):
            self.status.text = 'Skriv nøyaktig 4 tall.'
            return

        state.code = code
        state.command_char = None
        state.status_char = None
        state.peripheral = None

        self.status.text = 'Starter Bluetooth…'

        if state.manager is None:
            state.delegate = Delegate.alloc().init()
            state.manager = CBCentralManager.alloc().initWithDelegate_queue_(
                state.delegate, None
            )
        else:
            service = CBUUID.UUIDWithString_(SERVICE_UUID)
            state.manager.scanForPeripheralsWithServices_options_([service], None)

    def send_search(self, sender):
        query = self.search.text.strip()

        if not query:
            self.status.text = 'Skriv noe i søkefeltet.'
            return

        send_json({'type': 'search', 'query': query})


v = MainView()
state.view = v
v.present('sheet')
