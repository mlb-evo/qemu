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
    'acc_standby': 'ACC — ожидание (код состояния 2)',
    'gap_near': 'ACC — короткая дистанция (код 1)',
    'gap_far': 'ACC — большая дистанция (код 5)',
    'acc_warning': 'ACC — предупреждение / AWV (код 1)',
    'acc_failure': 'ACC — запрос сообщения о неисправности',
    'traffic_jam': 'Пробка / STA — индикация (код 1)',
    'lane_standby': 'Lane Assist — ожидание (лампы: код 1)',
    'limiter_warning': 'Ограничитель — подсказка водителю (код 1)',
    'sign_single': 'Знаки — один знак (сырой код 1)',
    'sign_three': 'Знаки — три знака (сырые коды 1 / 2 / 3)',
    'sign_warning': 'Знаки — предупреждение по первому знаку',
    'sign_timeout': 'Знаки — потеря данных',
    'sign_error': 'Знаки — ошибка данных',
    'night_active': 'Night Vision — включён',
    'night_pedestrian': 'Night Vision — предупреждение о пешеходе',
    'night_animal': 'Night Vision — предупреждение о животном',
    'night_pedestrian_off': 'Night Vision — предупреждение о пешеходах отключено',
    'night_timeout': 'Night Vision — потеря данных',
    'traffic_red': 'Светофор — красный',
    'traffic_green': 'Светофор — зелёный',
    'traffic_countdown': 'Светофор — ожидание зелёного',
    'traffic_speed': 'Светофор — рекомендуемая скорость',
    'traffic_unavailable': 'Светофор — нет данных',
}


# These describe display requests, not camera recognition or proven rendering.
DETAILS = {
    'sign_single': 'VZE_01: знак 1, режим 1. Значение кода знака ещё не расшифровано.',
    'sign_three': 'VZE_01: три сырых кода и дополнительные таблички 1 / 2 / 3; режим 1.',
    'sign_warning': 'VZE и ACC одновременно запрашивают предупреждение по первому знаку.',
    'sign_timeout': 'VZE_Timeout: timeout=1; коды знаков очищены.',
    'sign_error': 'VZE_Timeout: timeout_fehler=1; коды знаков очищены.',
}


def description(key):
    if key.startswith('traffic_') and key != 'traffic_jam':
        return ('Локальная BAP-сессия OnlineFunctions: сигнал, время до зелёного и скорость. '
                'На время пресета включается доступность OnlineFunctions; при выходе восстанавливается.')
    if key.startswith('night_'):
        return ('Запрос индикации Night Vision. Нужны доступность системы и её экран; '
                'видеопоток камеры и рамки объектов пока не подаются. '
                'Распознавание изображения этот пресет не выполняет.')
    if key.startswith('sign_'):
        return (DETAILS[key] + ' Показ зависит от кодировки и активного экрана. '
                'Это входы распознанных знаков, не распознавание камеры.')
    if key == 'off':
        return 'Очистить входы предыдущего сценария и остановить их передачу.'
    return ('Связанные запросы индикации отправляются вместе. Числа — коды прошивки, '
            'включая скорость; показ новых состояний требует проверки в госте.')


def scenario(key):
    if key not in LABELS:
        raise ValueError(f'Unknown assist scenario: {key}')
    if key == 'off':
        return {}
    from hmi.traffic_lights import PROFILES
    if key in PROFILES:
        return {}
    if key.startswith('sign_'):
        signs = {} if key in ('sign_timeout', 'sign_error') else dict(
            VZE_Verkehrszeichen_1_uint8=1, VZE_Anzeigemodus_uint8=1,
            VZE_Statuszaehler_1_uint8=1)
        result = {'VZE_01': signs, 'VZE_Timeout': dict(
            s_vze_timeout_uint8=int(key == 'sign_timeout'),
            s_vze_timeout_fehler_uint8=int(key == 'sign_error'))}
        if key == 'sign_three':
            signs.update(VZE_Verkehrszeichen_2_uint8=2, VZE_Verkehrszeichen_3_uint8=3,
                VZE_Zusatzschild_1_uint8=1, VZE_Zusatzschild_2_uint8=2,
                VZE_Zusatzschild_3_uint8=3, VZE_Statuszaehler_2_uint8=1,
                VZE_Statuszaehler_3_uint8=1)
        if key == 'sign_warning':
            signs['VZE_Warnung_Verkehrszeichen_1_uint8'] = 1
            result['ACC_12'] = dict(ACC_Warnung_Verkehrszeichen_1_uint8=1)
        return result
    if key.startswith('night_'):
        return {'HMI_C_NightVision_Display': dict(NV_aktiv_uint8=1,
            NV_Symbol_uint8=int(key == 'night_pedestrian'),
            NV_Symbol_Tierwarnung_uint8=int(key == 'night_animal'),
            NV_FGM_deaktiviert_Icon_uint8=int(key == 'night_pedestrian_off'),
            NV_Detected_Timeout_uint8=int(key == 'night_timeout'))}
    base = {'acc_standby': 'acc', 'gap_near': 'gap', 'gap_far': 'gap',
            'acc_warning': 'follow', 'acc_failure': 'acc', 'traffic_jam': 'acc_lane',
            'lane_standby': 'lane', 'limiter_warning': 'limiter'}.get(key)
    if base:
        result = scenario(base)
        hmi, legacy = result['ACC_HMI_Display'], result['ACC_02']
        if key == 'acc_standby':
            hmi['acc_SystemStatus_uint8'] = legacy['ACC_Status_Anzeige_uint8'] = 2
        if key in ('gap_near', 'gap_far'):
            hmi['acc_SetTimeGap_uint8'] = legacy['ACC_Gesetzte_Zeitluecke_uint8'] = (
                1 if key == 'gap_near' else 5)
        if key == 'acc_warning':
            hmi.update(awv_Warning_uint16=1, acc_WarningAnnouncement_b=1)
            legacy['ACC_Optischer_Fahrerhinweis_uint8'] = 1
        if key == 'acc_failure':
            hmi.update(acc_FailureNotification_b=1, acc_ErrorNotificationActive_b=1)
        if key == 'traffic_jam':
            hmi['sta_DisplayStatus_uint16'] = 1
            result['ACC_12']['STA_Primaeranz_uint8'] = 1
            result['ACC_14']['STA_Statusanzeige_uint8'] = 1
            result['TelltaleAALA_Display']['tt_sta_uint8'] = 2
        if key == 'lane_standby':
            result['TelltaleAALA_Display'].update(tt_lane_left_uint8=1, tt_lane_right_uint8=1)
            result['LDW_02'] = dict(LDW_Lernmodus_seitenabhaengig_uint8=1)
        if key == 'limiter_warning':
            result['TSK_07']['TSK_Limiter_Fahrerinfo_uint8'] = 1
        return result
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
