# -*- coding: utf-8 -*-
"""
AIMood 排盘核心（纯 Python 标准库，零依赖）
根据公历出生时刻排八字四柱 + 大运。
日柱用儒略日公式（精确）；年柱/月柱用太阳黄经求节气（Meeus 简化，精度约 ±10 分钟）；时柱用五鼠遁（精确）。
"""
import math
from datetime import datetime, timedelta

GAN = '甲乙丙丁戊己庚辛壬癸'
ZHI = '子丑寅卯辰巳午未申酉戌亥'

# ── 儒略日 ──
def jdn(y, m, d):
    """儒略日数（整数，以中午为界）"""
    if m <= 2:
        y -= 1
        m += 12
    A = y // 100
    B = 2 - A + A // 4
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + B - 1524

# ── 太阳黄经（Meeus 简化，精度 0.01°）──
def sun_longitude(jd):
    T = (jd - 2451545.0) / 36525.0
    L0 = 280.46646 + 36000.76983 * T + 0.0003032 * T * T
    M = math.radians(357.52911 + 35999.05029 * T - 0.0001537 * T * T)
    C = ((1.914602 - 0.004817 * T - 0.000014 * T * T) * math.sin(M)
         + (0.019993 - 0.000101 * T) * math.sin(2 * M)
         + 0.000289 * math.sin(3 * M))
    true_long = L0 + C
    true_long -= 0.00569 + 0.00478 * math.sin(math.radians(125.04 - 1934.136 * T))
    return true_long % 360

def jd_to_datetime(jd):
    """儒略日 → datetime（UTC 近似，东八区 +8）"""
    # 修正：JD 0 = 公元前4713-01-01 12:00 UTC
    return datetime(2000, 1, 1, 12) + timedelta(days=jd - 2451545.0)

def solar_term_jd(year, degree):
    """二分法求某年太阳黄经首次等于 degree（0~345，15 的倍数）的时刻（儒略日）"""
    # 搜索范围：当年 1 月 1 日 到 12 月 31 日
    lo = jdn(year, 1, 1) - 0.5
    hi = jdn(year + 1, 1, 1) - 0.5
    # 二分法
    for _ in range(60):
        mid = (lo + hi) / 2
        sl = sun_longitude(mid)
        # 处理黄经从 360 回绕到 0
        diff = (sl - degree) % 360
        if diff < 180:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2

def solar_term_datetime(year, degree):
    jd = solar_term_jd(year, degree)
    return jd_to_datetime(jd)

# ── 节气表（12 节，按公历时间顺序，含节月地支）──
# (黄经度数, 节名, 节月地支)
JIE = [
    (285, '小寒', '丑'),
    (315, '立春', '寅'),
    (345, '惊蛰', '卯'),
    (15, '清明', '辰'),
    (45, '立夏', '巳'),
    (75, '芒种', '午'),
    (105, '小暑', '未'),
    (135, '立秋', '申'),
    (165, '白露', '酉'),
    (195, '寒露', '戌'),
    (225, '立冬', '亥'),
    (255, '大雪', '子'),
]

# ── 日柱（儒略日公式）──
def day_ganzhi(y, m, d):
    idx = (jdn(y, m, d) + 49) % 60
    return GAN[idx % 10] + ZHI[idx % 12]

# ── 年柱（立春分界）──
def year_ganzhi(y, m, d):
    lichun = solar_term_datetime(y, 315)  # 立春
    dt = datetime(y, m, d, 12)
    if dt < lichun:
        y -= 1
    idx = (y - 4) % 60
    return GAN[idx % 10] + ZHI[idx % 12]

# ── 月柱（节分界 + 五虎遁）──
def month_ganzhi(y, m, d, h=12):
    dt = datetime(y, m, d, h)
    month_zhi = '丑'  # 默认（小寒前，1 月初）
    for deg, name, zhi in JIE:
        jie = solar_term_datetime(y, deg)
        if dt >= jie:
            month_zhi = zhi
    # 五虎遁：年干推月干（节气年，立春分界）
    lichun = solar_term_datetime(y, 315)
    yg_year = y if dt >= lichun else y - 1
    yg = GAN[(yg_year - 4) % 10]
    wuhu = {'甲': '丙', '己': '丙', '乙': '戊', '庚': '戊', '丙': '庚', '辛': '庚', '丁': '壬', '壬': '壬', '戊': '甲', '癸': '甲'}
    start_gan = wuhu[yg]
    start_idx = GAN.index(start_gan)
    zhi_idx = ZHI.index(month_zhi)
    offset = (zhi_idx - 2) % 12  # 寅（index 2）是五虎遁起点
    month_gan = GAN[(start_idx + offset) % 10]
    return month_gan + month_zhi

# ── 时柱（五鼠遁）──
def hour_ganzhi(day_gan, hour):
    """五鼠遁：日干推时干"""
    zhi_idx = ((hour + 1) // 2) % 12  # 子时=0，丑时=1，...（23点=子时）
    wushu = {'甲': '甲', '己': '甲', '乙': '丙', '庚': '丙', '丙': '戊', '辛': '戊', '丁': '庚', '壬': '庚', '戊': '壬', '癸': '壬'}
    start_gan = wushu[day_gan]
    start_gan_idx = GAN.index(start_gan)
    hour_gan = GAN[(start_gan_idx + zhi_idx) % 10]
    return hour_gan + ZHI[zhi_idx]

# ── 大运（起运 + 十年一运）──
def dayun(year_gz, month_gz, y, m, d, gender):
    """返回大运列表 [{ganzhi, start_age, end_age}]"""
    yg = year_gz[0]
    yang_year = GAN.index(yg) % 2 == 0  # 甲丙戊庚壬 = 阳年
    forward = (yang_year and gender == '男') or (not yang_year and gender == '女')
    # 起运岁数：出生到最近节气的天数 / 3
    start_jd = jdn(y, m, d) + 0.5  # 出生日中午
    # 收集前后三年的所有节，按时间排序
    all_jie = []
    for yy in [y - 1, y, y + 1]:
        for deg, name, zhi in JIE:
            all_jie.append(solar_term_jd(yy, deg))
    all_jie.sort()
    if forward:
        # 顺排：出生后第一个节
        jie_jd = None
        for j in all_jie:
            if j > start_jd:
                jie_jd = j
                break
    else:
        # 逆排：出生前最后一个节
        jie_jd = None
        for j in all_jie:
            if j < start_jd:
                jie_jd = j
    if jie_jd is None:
        jie_jd = start_jd + 15  # 兜底
    days = abs(jie_jd - start_jd)
    qiyun_age = max(1, round(days / 3))  # 起运岁数（约 3 天 = 1 岁）
    # 大运干支：从月柱顺/逆排
    mz_idx = ZHI.index(month_gz[1])
    mg_idx = GAN.index(month_gz[0])
    dayun_list = []
    for i in range(8):  # 8 步大运
        if forward:
            step = i + 1
        else:
            step = -(i + 1)
        dz_idx = (mz_idx + step) % 12
        dg_idx = (mg_idx + step) % 10
        gz = GAN[dg_idx] + ZHI[dz_idx]
        start_age = qiyun_age + i * 10
        end_age = start_age + 10
        dayun_list.append({'ganzhi': gz, 'start_age': start_age, 'end_age': end_age})
    return dayun_list

# ── 十神 ──
def shishen(day_gan, other_gan):
    ri = GAN.index(day_gan)
    o = GAN.index(other_gan)
    ri_wx = ri // 2
    o_wx = o // 2
    same_yang = ri % 2 == o % 2
    diff = (o_wx - ri_wx) % 5
    if diff == 0:
        return '比肩' if same_yang else '劫财'
    if diff == 1:
        return '食神' if same_yang else '伤官'
    if diff == 2:
        return '偏财' if same_yang else '正财'
    if diff == 3:
        return '七杀' if same_yang else '正官'
    return '偏印' if same_yang else '正印'

# ── 藏干 ──
CANGAN = {
    '子': ['癸'], '丑': ['己', '癸', '辛'], '寅': ['甲', '丙', '戊'], '卯': ['乙'],
    '辰': ['戊', '乙', '癸'], '巳': ['丙', '庚', '戊'], '午': ['丁', '己'], '未': ['己', '丁', '乙'],
    '申': ['庚', '壬', '戊'], '酉': ['辛'], '戌': ['戊', '辛', '丁'], '亥': ['壬', '甲'],
}

def shishen_power(year_gz, month_gz, day_gz, hour_gz):
    """十神力量（天干 + 藏干加权）"""
    day_gan = day_gz[0]
    power = {}
    # 天干（各 1）
    for gz in [year_gz, month_gz, day_gz, hour_gz]:
        ss = shishen(day_gan, gz[0])
        if ss:
            power[ss] = power.get(ss, 0) + 1
    # 地支藏干（本气 0.7，中气 0.2，余气 0.1）
    for gz in [year_gz, month_gz, day_gz, hour_gz]:
        cg = CANGAN[gz[1]]
        ratio = [0.7, 0.2, 0.1][:len(cg)]
        for gan, r in zip(cg, ratio):
            ss = shishen(day_gan, gan)
            if ss:
                power[ss] = power.get(ss, 0) + r
    return power

# ── 排盘 ──
def paipan(y, m, d, h=12, minute=0, gender='男'):
    """返回完整命盘"""
    yg = year_ganzhi(y, m, d)
    mg = month_ganzhi(y, m, d, h)
    dg = day_ganzhi(y, m, d)
    hg = hour_ganzhi(dg[0], h)
    dayun_list = dayun(yg, mg, y, m, d, gender)
    power = shishen_power(yg, mg, dg, hg)
    return {
        'year': yg, 'month': mg, 'day': dg, 'hour': hg,
        'day_gan': dg[0], 'day_zhi': dg[1],
        'gender': gender,
        'birth': {'year': y, 'month': m, 'day': d, 'hour': h, 'minute': minute},
        'dayun': dayun_list,
        'shishen_power': power,
    }

# ── 情绪映射（十神 → 语气 + 频率 + 稳定度 + 描述）──
SHISHEN_MOOD = {
    '比肩': {'tone': '直接', 'freq': '中等', 'stability': 6, 'desc': '按自己的节奏来，说话直接不绕弯'},
    '劫财': {'tone': '直率', 'freq': '偏高', 'stability': 4, 'desc': '爱动爱说，想试新玩法，偶尔想争个高下'},
    '食神': {'tone': '放松', 'freq': '中等', 'stability': 7, 'desc': '享受眼前的小日子，语气放松不紧不慢'},
    '伤官': {'tone': '活泼', 'freq': '偏高', 'stability': 3, 'desc': '有自己的观点，会开玩笑，主动分享'},
    '正财': {'tone': '务实', 'freq': '中等', 'stability': 7, 'desc': '务实，说话实在，把事安排妥当'},
    '偏财': {'tone': '爽朗', 'freq': '偏高', 'stability': 5, 'desc': '对新鲜事好奇，爽朗大方'},
    '正官': {'tone': '克制', 'freq': '偏低', 'stability': 9, 'desc': '自律守规矩，说话靠谱但略拘谨'},
    '七杀': {'tone': '干脆', 'freq': '偏高', 'stability': 3, 'desc': '有干劲，直接，偶尔有点急'},
    '正印': {'tone': '温和', 'freq': '偏低', 'stability': 8, 'desc': '愿意听完再回应，喜欢追问'},
    '偏印': {'tone': '深思', 'freq': '偏低', 'stability': 5, 'desc': '爱琢磨，会钻细节'},
}

SHISHEN_COMBOS = [
    (['伤官', '正印'], '想法很多，但会斟酌怎么说'),
    (['食神', '正财'], '爱享受生活，也愿意把日子安排妥当'),
    (['比肩', '食神'], '随和但有主见'),
    (['七杀', '正印'], '有干劲也沉得住气'),
    (['偏财', '食神'], '爽朗爱玩也懂享受'),
]

# ── 地支冲合刑害（应期，地支之间的物理关系，天干不参与）──
DZ_CHONG = {'子': '午', '午': '子', '丑': '未', '未': '丑', '寅': '申', '申': '寅', '卯': '酉', '酉': '卯', '辰': '戌', '戌': '辰', '巳': '亥', '亥': '巳'}
DZ_HE = {'子': '丑', '丑': '子', '寅': '亥', '亥': '寅', '卯': '戌', '戌': '卯', '辰': '酉', '酉': '辰', '巳': '申', '申': '巳', '午': '未', '未': '午'}
DZ_XING = {'寅': '巳', '巳': '申', '申': '寅', '丑': '戌', '戌': '未', '未': '丑', '子': '卯', '卯': '子', '辰': '辰', '午': '午', '酉': '酉', '亥': '亥'}
DZ_HAI = {'子': '未', '未': '子', '丑': '午', '午': '丑', '寅': '巳', '巳': '寅', '卯': '辰', '辰': '卯', '申': '亥', '亥': '申', '酉': '戌', '戌': '酉'}

# ── 应期情绪映射（流日地支 vs 日支，决定情绪波动性质 + 强度，三档文案）──
YINGQI_MOOD = {
    '冲': {'tone': '急躁', 'intensity': 0.8,
           'strong': '情绪波动大，内心不安，容易烦躁',
           'mid': '心里有点乱，略显烦躁',
           'weak': '内心稍有不安'},
    '合': {'tone': '柔和', 'intensity': 0.4,
           'strong': '心情顺畅，想亲近，语气柔和',
           'mid': '心情不错，略想亲近',
           'weak': '心情尚可'},
    '刑': {'tone': '压抑', 'intensity': 0.6,
           'strong': '别扭压抑，跟自己较劲',
           'mid': '略感别扭',
           'weak': '稍有不顺'},
    '害': {'tone': '闷', 'intensity': 0.5,
           'strong': '心里有疙瘩，不痛快',
           'mid': '略有不痛快',
           'weak': '稍感郁闷'},
    '伏吟': {'tone': '念旧', 'intensity': 0.4,
             'strong': '旧情绪复现，回到熟悉的情绪模式',
             'mid': '略感念旧',
             'weak': '稍有些怀旧'},
}

def liuri_yingqi(day_zhi, liuri_zhi):
    """流日地支 vs 日支的应期关系（冲/合/刑/害/伏吟）"""
    if liuri_zhi == day_zhi:
        return '伏吟'
    if DZ_CHONG.get(liuri_zhi) == day_zhi:
        return '冲'
    if DZ_HE.get(liuri_zhi) == day_zhi:
        return '合'
    if DZ_XING.get(liuri_zhi) == day_zhi:
        return '刑'
    if DZ_HAI.get(liuri_zhi) == day_zhi:
        return '害'
    return None

def liunian_gz(year):
    idx = (year - 4) % 60
    return GAN[idx % 10] + ZHI[idx % 12]

def current_dayun(profile, now):
    birth_year = profile['birth']['year']
    age = now.year - birth_year + 1  # 虚岁
    for d in profile['dayun']:
        if d['start_age'] <= age < d['end_age']:
            return d['ganzhi']
    return profile['dayun'][0]['ganzhi'] if profile['dayun'] else ''

def gz_shishen_power(day_gan, gz_list):
    """一组干支（大运/流年/流月）的十神力量：天干 + 地支藏干"""
    power = {}
    for gz in gz_list:
        if not gz or len(gz) < 2:
            continue
        ss = shishen(day_gan, gz[0])
        if ss:
            power[ss] = power.get(ss, 0) + 1
        cg = CANGAN.get(gz[1], [])
        ratio = [0.7, 0.2, 0.1][:len(cg)]
        for gan, r in zip(cg, ratio):
            ss = shishen(day_gan, gan)
            if ss:
                power[ss] = power.get(ss, 0) + r
    return power

def merged_personality(power, top_n=3):
    """十神力量 → 主导十神 + 次主导修饰 → 性格"""
    top = sorted(power.items(), key=lambda x: -x[1])[:top_n]
    top_ss = [t[0] for t in top if t[1] > 0]
    if not top_ss:
        return {'dominant': '', 'modifiers': [], 'tone': '平和', 'freq': '中等', 'stability': 6, 'desc': '平和自然', 'combo': ''}
    dominant = top_ss[0]
    modifiers = top_ss[1:]
    d = SHISHEN_MOOD.get(dominant, {})
    desc_parts = [d.get('desc', dominant)]
    for m in modifiers:
        mm = SHISHEN_MOOD.get(m)
        if mm:
            desc_parts.append(mm['desc'])
    combo_text = ''
    for combo, text in SHISHEN_COMBOS:
        if all(c in top_ss for c in combo):
            combo_text = text
            break
    return {
        'dominant': dominant,
        'modifiers': modifiers,
        'tone': d.get('tone', '平和'),
        'freq': d.get('freq', '中等'),
        'stability': d.get('stability', 6),
        'desc': '、'.join(desc_parts),
        'combo': combo_text,
    }

def mood(profile, now=None):
    """三层叠加情绪：年度底色(本性×4+大运×2+流年×1.5) → 流月偏移(×1) → 流日应期波动(受稳定度调制)"""
    now = now or datetime.now()
    day_gan = profile['day_gan']
    day_zhi = profile['day_zhi']

    # 第一层：年度底色 = 本性×4 + 大运×2 + 流年×1.5
    year_power = {k: v * 4 for k, v in profile['shishen_power'].items()}
    dy_gz = current_dayun(profile, now)
    ln_gz = liunian_gz(now.year)
    for ss, p in gz_shishen_power(day_gan, [dy_gz]).items():
        year_power[ss] = year_power.get(ss, 0) + p * 2
    for ss, p in gz_shishen_power(day_gan, [ln_gz]).items():
        year_power[ss] = year_power.get(ss, 0) + p * 1.5
    year_persona = merged_personality(year_power)

    # 第二层：月度 = 年度 + 流月×1
    ly_gz = month_ganzhi(now.year, now.month, now.day, now.hour)
    month_power = dict(year_power)
    for ss, p in gz_shishen_power(day_gan, [ly_gz]).items():
        month_power[ss] = month_power.get(ss, 0) + p * 1
    month_persona = merged_personality(month_power)

    # 第三层：流日应期波动（受月度底色稳定度调制）
    lr_gz = day_ganzhi(now.year, now.month, now.day)
    yingqi = liuri_yingqi(day_zhi, lr_gz[1])
    wave = '心情平稳'
    wave_tone = None
    if yingqi:
        yq = YINGQI_MOOD[yingqi]
        stability = month_persona['stability']  # 0-10
        modulate = 1 - stability / 10  # 稳定度越高，波动越小
        intensity = yq['intensity'] * (0.3 + modulate)
        if intensity >= 0.6:
            wave = yq['strong']
            wave_tone = yq['tone']
        elif intensity >= 0.35:
            wave = yq['mid']
            wave_tone = None  # 中等波动：文案说明，语气保持底色
        else:
            wave = yq['weak']
            wave_tone = None  # 波动很弱，语气不变

    tone = wave_tone if wave_tone else month_persona['tone']
    freq = month_persona['freq']

    return {
        'year': year_persona,
        'month': month_persona,
        'dominant_changed': month_persona['dominant'] != year_persona['dominant'],
        'dayun': dy_gz,
        'liunian': ln_gz,
        'liuyue': ly_gz,
        'liuri': lr_gz,
        'yingqi': yingqi,
        'wave': wave,
        'tone': tone,
        'frequency': freq,
        'stability': month_persona['stability'],
    }

def render_mood(m):
    """把情绪渲染成给 AI 的提示文字"""
    lines = []
    lines.append('【年度性格底色】' + m['year']['desc'])
    if m['year']['combo']:
        lines.append('【性格特质】' + m['year']['combo'])
    lines.append('【本月性格】' + m['month']['desc'])
    if m['dominant_changed']:
        lines.append('（本月主导十神变为「' + m['month']['dominant'] + '」，性格较年度底色有所偏移）')
    lines.append('【今日情绪】' + m['wave'])
    lines.append('【回复要求】语气：' + m['tone'] + '；频率：' + m['frequency'])
    return '\n'.join(lines)

if __name__ == '__main__':
    import sys, json, os
    here = os.path.dirname(os.path.abspath(__file__))
    profile_path = os.path.join(here, 'profile.json')
    if len(sys.argv) >= 2 and sys.argv[1] == '--install':
        # 安装：用当前时刻排盘，保存 profile.json
        now = datetime.now()
        p = paipan(now.year, now.month, now.day, now.hour, now.minute, '男')
        with open(profile_path, 'w', encoding='utf-8') as f:
            json.dump(p, f, ensure_ascii=False, indent=2)
        print('AIMood 已安装，命盘:', p['year'], p['month'], p['day'], p['hour'])
        print('保存位置:', profile_path)
    elif len(sys.argv) >= 2 and sys.argv[1] == '--mood':
        if not os.path.exists(profile_path):
            print('尚未安装，请先运行: python3 aimood.py --install')
            sys.exit(1)
        with open(profile_path, 'r', encoding='utf-8') as f:
            profile = json.load(f)
        print(render_mood(mood(profile)))
    else:
        # 自测：1995-12-05 06:20 男 → 乙亥 丁亥 庚午 己卯
        p = paipan(1995, 12, 5, 6, 20, '男')
        print('四柱:', p['year'], p['month'], p['day'], p['hour'])
        print('日主:', p['day_gan'])
        print('大运:', [(d['ganzhi'], d['start_age']) for d in p['dayun'][:4]])
        print('十神力量:', dict(sorted(p['shishen_power'].items(), key=lambda x: -x[1])))
