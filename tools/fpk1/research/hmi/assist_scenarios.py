"""Coherent local display fixtures; not models of the real assist ECUs.

Populate both legacy ACC and HMI display requests consistently. In original
gtf2, FAS::updateAccPopupRequest (0x1ddd58) requires the time-gap request;
availability, lamps and speed alone do not request that view.
"""
import sys
sys.dont_write_bytecode = True
from copy import deepcopy

LABELS = {
    'off': 'Выключить ассистенты',
    'acc': 'ACC — заданная скорость',
    'follow': 'ACC — автомобиль впереди',
    'gap': 'ACC — дистанция',
    'lane': 'Lane Assist — обе линии',
    'lane_left': 'Lane Assist — левая линия',
    'lane_right': 'Lane Assist — правая линия',
    'acc_lane': 'ACC + Lane Assist',
    'cruise': 'Круиз-контроль',
    'limiter': 'Ограничитель скорости',
}


def scenario(key):
    if key not in LABELS:
        raise ValueError(f'Unknown assist scenario: {key}')
    if key == 'off':
        return {}
    result = {'ACC_KBI': {'available': 1}, 'TelltaleAALA_Display': {},
              'ACC_HMI_Display': {}, 'ACC_02': {}, 'ACC_12': {}, 'ACC_14': {},
              'ACC_13_HMIStatus': {}, 'ACC_HMI_Ring': {}, 'LDW_02': {}, 'TSK_07': {}}
    lamps = result['TelltaleAALA_Display']
    acc = key in ('acc', 'follow', 'gap', 'acc_lane')
    lane = key in ('lane', 'lane_left', 'lane_right', 'acc_lane')
    if acc:
        car = 1 if key == 'follow' else 0
        result['ACC_HMI_Display'] = dict(acc_Availability_b=1, acc_SystemStatus_uint8=3,
            acc_desiredSpeed_uint16=100, acc_SetTimeGap_uint8=3, acc_DistanceIndex_uint16=3,
            acc_DisplayVehicle_uint8=car, acc_DisplayTimeGap_b=1)
        result['ACC_02'] = dict(ACC_Status_Anzeige_uint8=3, ACC_Wunschgeschw_uint16=100,
            ACC_Gesetzte_Zeitluecke_uint8=3, ACC_Abstandsindex_uint16=3,
            ACC_Relevantes_Objekt_uint8=car, ACC_Anzeige_Zeitluecke_uint8=1,
            ACC_Tachokranz_uint8=1)
        result['ACC_12'] = dict(ACC_EGO_Fahrzeug_uint8=1,
                               ACC_rel_Objekt_Zusatzanz_uint8=car)
        result['ACC_HMI_Ring'] = dict(acc_MaxSetSpeedKmph_uint16=200,
                                    acc_MaxSetSpeedMph_uint16=125)
        lamps.update(tt_acc_radar_uint8=2, tt_ldw_acc_egoCar_uint8=2,
                     tt_acc_vorFzg_uint8=2 if car else 0)
        if key == 'gap':
            result['ACC_HMI_Display']['acc_SetTimeGap_uint8'] = 4
            result['ACC_02']['ACC_Gesetzte_Zeitluecke_uint8'] = 4
    if lane:
        # Paired telltale requests and LDW state are changed together.
        left = 3 if key == 'lane_left' else 2
        right = 3 if key == 'lane_right' else 2
        lamps.update(tt_lane_left_uint8=left, tt_lane_right_uint8=right,
                     tt_ldw_acc_egoCar_uint8=2)
        result['LDW_02'] = dict(LDW_Lernmodus_seitenabhaengig_uint8=3,
                               LDW_Status_LED_gruen_uint8=1,
                               LDW_Status_LED_gelb_uint8=int(key in ('lane_left', 'lane_right')))
    if key in ('cruise', 'limiter'):
        limiter = key == 'limiter'
        result['TSK_07'] = dict(TSK_Wunschgeschw_uint16=80 if limiter else 100,
                               TSK_Status_Anzeige_uint8=3, TSK_Limiter_Anzeige_uint8=int(limiter))
        lamps['tt_limiter_uint8' if limiter else 'tt_gra_uint8'] = 2
    return deepcopy(result)
