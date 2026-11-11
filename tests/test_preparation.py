"""Run: python -m unittest discover -s tests -v (requires aiohttp).

Small HA import stand-ins let the real API client run without a live HA instance.
All HTTP dispatches are mocked; no vehicle commands are sent.
"""
import importlib
import sys
import types
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

class EnumNames(type):
    def __getattr__(cls, name):
        return name.lower()

for name in ('homeassistant', 'homeassistant.util', 'homeassistant.components',
             'homeassistant.components.sensor', 'homeassistant.components.binary_sensor'):
    sys.modules.setdefault(name, types.ModuleType(name))
for module, names in [('sensor', ('SensorDeviceClass', 'SensorStateClass')),
                      ('binary_sensor', ('BinarySensorDeviceClass',))]:
    for name in names:
        setattr(sys.modules['homeassistant.components.'+module],name,EnumNames(name,(),{}))
sys.modules['homeassistant.util'].dt = types.SimpleNamespace(
    utc_from_timestamp=lambda ts:datetime.fromtimestamp(ts,timezone.utc),
    parse_datetime=lambda value:datetime.fromisoformat(value),
)
pkg=types.ModuleType('evolute_under_test')
pkg.__path__=[str(Path(__file__).resolve().parents[1]/'custom_components/evolute')]
sys.modules[pkg.__name__]=pkg
client=importlib.import_module(pkg.__name__+'.client')
const=importlib.import_module(pkg.__name__+'.const')

RAW={
    'isOnline': True,
    'sensors': {'isParkedOn':True,'isCentralLockingOn':True},
    'buttons': [{'tag':'trip-preparation','activateCommand':'tripPreparationOn',
                 'deactivateCommand':'tripPreparationOff','status':False,'enabled':True,
                 'lastRun':{'startedAt':1794422295029,'durationMs':1019980,'isActive':False}}],
}

class TelemetryTests(unittest.TestCase):
    def test_ordinary_account_can_prepare(self):
        raw=deepcopy(RAW)
        raw.update(isSuperAdmin=False,canViewTaggedCarButtons=False)
        data=client._parse_car_info_v2(raw)
        self.assertTrue(data['prep_available'])
        self.assertFalse(data['prep_running'])
        self.assertNotIn(const.COMMAND_PREPARE,data[const.DISABLED_COMMANDS_KEY])
        self.assertIn(const.COMMAND_CANCEL,data[const.DISABLED_COMMANDS_KEY])
        self.assertEqual(data['prep_start_time'].timestamp(),1794422295.029)

    def test_active_disabled_button_still_allows_cancel(self):
        raw=deepcopy(RAW);raw['buttons'][0].update(status=True,enabled=False)
        data=client._parse_car_info_v2(raw)
        self.assertTrue(data['prep_running'])
        self.assertIn(const.COMMAND_PREPARE,data[const.DISABLED_COMMANDS_KEY])
        self.assertNotIn(const.COMMAND_CANCEL,data[const.DISABLED_COMMANDS_KEY])

    def test_vehicle_gates_preserved(self):
        for field,value in [('isOnline',False),('isParkedOn',False),('isCentralLockingOn',False)]:
            with self.subTest(field=field):
                raw=deepcopy(RAW)
                (raw if field=='isOnline' else raw['sensors'])[field]=value
                data=client._parse_car_info_v2(raw)
                self.assertIn(const.COMMAND_PREPARE,data[const.DISABLED_COMMANDS_KEY])
                self.assertIsNotNone(data['command_block_reason'])

    def test_missing_preparation_button_does_not_offer_start(self):
        raw=deepcopy(RAW);raw['buttons']=[]
        data=client._parse_car_info_v2(raw)
        self.assertIn(const.COMMAND_PREPARE,data[const.DISABLED_COMMANDS_KEY])

    def test_no_last_run_is_unknown(self):
        raw=deepcopy(RAW);raw['buttons'][0].pop('lastRun')
        self.assertIsNone(client._parse_car_info_v2(raw)['prep_start_time'])

class DispatchTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.api=client.EvoluteClient(None,'unused','unused')
        self.api._imeis['car']='test-imei'
        self.api._buttons['car']=deepcopy(RAW['buttons'])

    async def test_start_reads_fresh_selected_duration(self):
        self.api._request=AsyncMock(side_effect=[
            {'currentScriptTime':120,'availableScriptTime':[5,15,30,60,90,120]},
            {'commandId':'accepted'},
        ])
        self.assertEqual(await self.api.async_send_command('car',const.COMMAND_PREPARE),(True,'accepted'))
        calls=self.api._request.call_args_list
        self.assertEqual(calls[0].args,('GET',const.BASE_URL+'/car-service/car/v2/car'))
        self.assertEqual(calls[1].kwargs['json_body'],
                         {'commandName':'tripPreparationOn','imei':'test-imei','durationMinutes':120})

    async def test_invalid_duration_never_dispatches(self):
        for details in [None,{}, {'currentScriptTime':True,'availableScriptTime':[True]},
                        {'currentScriptTime':0,'availableScriptTime':[0]},
                        {'currentScriptTime':30,'availableScriptTime':[15]},
                        {'currentScriptTime':30},
                        {'currentScriptTime':'30','availableScriptTime':[30]}]:
            with self.subTest(details=details):
                self.api._request=AsyncMock(return_value=details)
                self.assertEqual(await self.api.async_send_command('car',const.COMMAND_PREPARE),(False,None))
                self.assertEqual(self.api._request.call_count,1)
                self.assertEqual(self.api._request.call_args.args[0],'GET')

    async def test_cancel_does_not_require_duration(self):
        self.api._buttons['car'][0]['status']=True
        self.api._request=AsyncMock(return_value={'commandId':'cancel'})
        self.assertEqual(await self.api.async_send_command('car',const.COMMAND_CANCEL),(True,'cancel'))
        self.api._request.assert_awaited_once_with('POST',const.TELEMETRY_COMMANDS_URL,
                json_body={'commandName':'tripPreparationOff','imei':'test-imei'})

    async def test_missing_button_never_dispatches(self):
        self.api._buttons['car']=[];self.api._request=AsyncMock()
        self.assertEqual(await self.api.async_send_command('car',const.COMMAND_PREPARE),(False,None))
        self.api._request.assert_not_awaited()

    async def test_server_rejection_does_not_retry_launch(self):
        self.api._request=AsyncMock(side_effect=[
            {'currentScriptTime':15,'availableScriptTime':[15]},None])
        self.assertEqual(await self.api.async_send_command('car',const.COMMAND_PREPARE),(False,None))
        self.assertEqual(self.api._request.call_count,2)

    async def test_legacy_dispatch_unchanged(self):
        self.api._no_v2.add('car');self.api._request=AsyncMock(return_value={})
        self.assertEqual(await self.api.async_send_command('car',const.COMMAND_PREPARE),(True,None))
        self.api._request.assert_awaited_once_with('POST',const.BASE_URL+'/car-service/tbox/car/PREPARE',json_body={})

    async def test_car_discovery_does_not_fetch_display_permissions(self):
        self.api._request=AsyncMock(return_value={'rows':[]})
        self.assertEqual(await self.api.async_get_cars(),[])
        self.api._request.assert_awaited_once()
        self.assertEqual(self.api._request.call_args.args[1],const.CAR_SEARCH_URL)

if __name__=='__main__':unittest.main()
