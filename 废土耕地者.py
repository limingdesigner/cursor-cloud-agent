# -*- coding: utf-8 -*-
"""
=============================================================================
    废土耕地者  Sinkland Cultivator
=============================================================================
游戏类型   ：废土题材塔防，玩法类似《植物大战僵尸》
核心玩法   ：玩家在废土建造基地，放置卡牌召唤防御单位（耕地者），
             抵御一波波怪物进攻，保护基地（左侧）。
设计原则   ：本文件采用【分区分类】结构，每个分区顶部有完整注释。
            后续【新增角色 / 新功能】时，只需：
                1) 在“二、单位/卡牌数据区”添加一条数据字典；
                2) 若该单位有新的行为，在“七、战斗实体区”的
                   Defender.update() 里按行为类型新增一个分支；
                3) 若有新的界面，在“九、场景区”新增一个场景类，
                   并在“十、主循环区”的场景字典里登记。
运行依赖   ：pygame（本机使用社区版 pygame-ce，安装命令：
             pip install pygame-ce）
=============================================================================
"""
import pygame
import random
import math
import sys
import os
import json

# ============================================================================
# 一、全局配置区：窗口 / 画布 / 颜色 / 网格 / 帧率等基础常量
# ============================================================================
# 【说明】改窗口尺寸、配色、网格行数列数时只改这里，全游戏自动生效。
SCREEN_WIDTH  = 1280     # 窗口宽度（扩大视野：5行×12列战场）
SCREEN_HEIGHT = 640      # 窗口高度
FPS           = 60       # 目标帧率

# --- 废土风格配色 ---
COLOR_BG       = (22, 24, 28)    # 主背景（灰暗废土）
COLOR_GRID     = (45, 48, 53)    # 网格线
COLOR_PANEL    = (34, 37, 42)    # 面板底色
COLOR_TEXT     = (235, 235, 240) # 主文字
COLOR_TEXT_DIM = (160, 163, 170) # 次要文字
COLOR_GOLD     = (255, 215, 80)  # 能源/金色
COLOR_CORE     = (80, 200, 255)  # 蓝色能源核心
COLOR_OLIVE    = (90, 100, 70)   # 橄榄绿
COLOR_BROWN    = (85, 70, 60)    # 头发
COLOR_RED      = (255, 80, 80)   # 警示
# ---- 伤害数字按伤害类型配色（用户需求）：物理灰 / 爆炸橙 / 火系红 / 冰系蓝 / 雷系紫 ----
DAMAGE_COLOR_PHYS = (185, 185, 195)   # 物理：钝击 / 切割 / 穿刺 / 怪物啃咬
DAMAGE_COLOR_BOOM = (255, 160, 60)    # 爆炸：凯恩SP大招大弹药
DAMAGE_COLOR_FIRE = (255, 110, 90)    # 火系：伊格尼斯爆炸 / 火区持续 / 灼烧
DAMAGE_COLOR_ICE  = (120, 200, 255)   # 冰系：白夜冰弹 / 大招 / 冻伤
DAMAGE_COLOR_BOLT = (185, 135, 255)   # 雷系：莱昂纳多电弧 / 雷暴
DAMAGE_COLOR_WATER = (70, 170, 255)  # 水系：卡斯珀高压水流 / 暗潮漩涡（与冰系区分）
DAMAGE_COLOR_POISON = (160, 225, 95) # 毒系：罗格SP腐毒形态 / 腐蚀持续伤害（毒绿色）
COLOR_GREEN    = (100, 220, 100) # 生命/就绪
COLOR_MONSTER  = (60, 55, 50)    # 怪物
COLOR_WHITE    = (255, 255, 255)
COLOR_BUTTON   = (70, 74, 82)    # 按钮
COLOR_BUTTON_H = (95, 100, 110)  # 按钮悬停

# --- 战场网格：5 行 × 9 列 ---
# 顶部保留 HUD 区（能量/波次），底部保留卡牌槽位区。
GRID_ROWS = 5
GRID_COLS = 12
HUD_HEIGHT      = 60   # 顶部信息条高度
CARD_BAR_HEIGHT = 110  # 底部卡牌槽位高度
GRID_TOP = HUD_HEIGHT
GRID_BOTTOM = SCREEN_HEIGHT - CARD_BAR_HEIGHT
GRID_LEFT = 0                # 网格左边界（网格左对齐屏幕左侧）
GRID_W = SCREEN_WIDTH
GRID_H = GRID_BOTTOM - GRID_TOP
CELL_W = GRID_W // GRID_COLS
CELL_H = GRID_H // GRID_ROWS

# --- 加载界面进度模拟 ---
LOAD_TOTAL_TICKS = 60   # 加载界面持续帧数（模拟加载资源进度）

# ============================================================================
# 二、单位 / 卡牌数据区（“数据驱动”核心）
# ============================================================================
# 【说明】每个耕地者（防御单位）是一条字典，字段含义：
#   uid        : 唯一标识（用于卡牌、部署）
#   name       : 名称
#   is_sp      : 是否为 SP（进阶）变体
#   sp_of      : SP 专属：对应普通形态的 uid（SP 只能种植在普通形态上替换升级）
#   desc       : 手册/图鉴里的介绍文字
#   cost       : 部署消耗能量
#   cd         : 部署冷却（秒）
#   hp / maxhp : 生命
#   behavior   : 行为类型（energy=产能源 / shooter=远程输出 / blocker=肉盾阻挡）
#                —— 后续新增行为只需在此标记新类型，并在 Defender.update 加分支
#   produce    : 常规能力数值
#   attack     : 攻击力（无则0）
#   atk_iv     : 攻击间隔（秒）
#   dmg_reduce : 常驻减伤比例（如布洛克0.5=减伤50%）
#   ult_name / ult_desc : 大招名称与说明
#   ult        : 大招数值
#   ult_cd     : 大招冷却（秒）
#   color      : 绘制主色
#   【后续新增角色】按同样格式复制一份字典即可，无需改动其他代码。
UNITS = [
    # ---- 里昂（能源生产位）----
    dict(uid="leon",    name="里昂",       is_sp=False,
         desc="废土基地首席建设者。每隔一段时间产出能源球，用鼠标拾取。",
         cost=50, cd=5, hp=300, behavior="energy",
         produce=50, produce_iv=12, attack=0, atk_iv=0,
         ult_name="黎明过载", ult_desc="立即产出300能源。", ult=300, ult_cd=40,
         color=(235, 235, 240)),
    dict(uid="leon_sp", name="里昂·SP",   is_sp=True, sp_of="leon",
         desc="过载核心的建设者，能源产出速度翻倍，是基地的能源引擎。",
         cost=100, cd=15, hp=450, behavior="energy",
         produce=50, produce_iv=6, attack=0, atk_iv=0,
         ult_name="永昼过载", ult_desc="立即产出600能源。", ult=600, ult_cd=40,
         color=(248, 248, 252)),
    # ---- 凯恩（远程输出位）----
    dict(uid="kain",    name="凯恩",       is_sp=False,
         desc="废土拾荒者出身的护卫，用气动投掷器发射钝击弹。",
         cost=75, cd=5, hp=400, behavior="shooter",
         produce=0, produce_iv=0, attack=35, atk_iv=1.2,
         ult_name="连发模式", ult_desc="接下来10次攻击0.4秒间隔连射。", ult=10, ult_cd=25,
         color=(90, 100, 70)),
    dict(uid="kain_sp", name="凯恩·SP",   is_sp=True, sp_of="kain",
         desc="重甲强化的护卫，双管投掷器，20%概率连发5枚。",
         cost=250, cd=15, hp=500, behavior="shooter",
         produce=0, produce_iv=0, attack=70, atk_iv=1.2,
         ult_name="毁灭连射", ult_desc="瞬间倾泻5枚大弹丸，单颗500伤害。", ult=500, ult_cd=25,
         color=(70, 66, 58)),
    # ---- 布洛克（肉盾/阻挡位）----
    dict(uid="brock",   name="布洛克",     is_sp=False,
         desc="前废土车队护卫队长。固守姿态常驻减伤50%，铁壁嘲讽吸引敌人。",
         cost=50, cd=20, hp=2000, behavior="blocker",
         produce=0, produce_iv=0, attack=0, atk_iv=0,
         dmg_reduce=0.5,
         ult_name="铁壁嘲讽", ult_desc="吸引自身行及相邻行敌人强制攻击自己4秒，并获得1000护盾。",
         ult=0, ult_cd=40,
         color=(120, 128, 140)),
    # ---- 伊格尼斯（火元素·一次性爆破位）----
    dict(uid="ignis",   name="伊格尼斯",   is_sp=False,
         desc="废土爆破组幸存者。投掷燃烧瓶烧出火区后跑路消失，无生命值无法被攻击。",
         cost=50, cd=20, hp=0, behavior="fire",
         produce=0, produce_iv=0, attack=0, atk_iv=0,
         fire_dmg=800, fire_dot=150, fire_sec=4, burn=100, burn_sec=4, fuse=30,
         ult_name="无大招（一次性）", ult_desc="投掷燃烧瓶造成爆炸+火区+灼烧后消失。",
         ult=0, ult_cd=0,
         color=(230, 90, 60)),
    # ---- 诺瓦（近战切割位）----
    dict(uid="nova",    name="诺瓦",       is_sp=False,
         desc="废土游荡者，手持荧光电锯的近战切割者。攻击自身格及前方3格内所有敌人。",
         cost=125, cd=10, hp=500, behavior="melee",
         produce=0, produce_iv=0, attack=60, atk_iv=5,
         range=3, swing_sec=4,
         ult_name="锯刃风暴", ult_desc="向前方突进4格，路径上敌人受5段×200切割伤害。",
         ult=200, ult_cd=30,
         color=(110, 150, 190)),
    # ---- 白夜（冰霜控制位）----
    dict(uid="baiye",   name="白夜",       is_sp=False,
         desc="废土前气象站观测员。凝霜弹附加减速，大招冰雨冻结前方大范围敌人。",
         cost=150, cd=12, hp=450, behavior="ice",
         produce=0, produce_iv=0, attack=50, atk_iv=2,
         ice=True, slow_pct=0.5, slow_sec=3,
         ult_name="极乐冰宴", ult_desc="自身行及相邻行前方5格：500冰伤+冻结3秒+冻伤100/秒。",
         ult=500, ult_cd=20,
         color=(170, 210, 235)),
    dict(uid="baiye_sp", name="白夜·SP",  is_sp=True, sp_of="baiye",
         desc="寒霜阵地管控者。白银冰破弹命中后3×3溅射50%冰伤，大招永夜展开冻结冰场。",
         cost=200, cd=12, hp=600, behavior="ice",
         produce=0, produce_iv=0, attack=100, atk_iv=2,
         ice=True, slow_pct=0.5, slow_sec=3, sp_splash=0.75,
         ult_name="永夜", ult_desc="自身行及相邻行前方展开冰场4秒：场内冻结+每秒600冰伤，释放期间自身无敌。",
         ult=600, ult_cd=20,
         color=(150, 200, 240)),
    # ---- 茯苓（治疗支援位）----
    dict(uid="fuling",  name="茯苓",       is_sp=False,
         desc="废土流浪药贩。每秒为自身及相邻格友方回复生命，大招喷出药雾群疗。",
         cost=100, cd=12, hp=600, behavior="healer",
         produce=0, produce_iv=0, attack=0, atk_iv=0,
         heal=50, heal_iv=1,
         ult_name="急救喷雾", ult_desc="前方3格范围友方：瞬间回300+每秒50持续4秒（总500）。",
         ult=300, ult_hot=50, ult_hot_sec=4, ult_cd=30,
         color=(190, 220, 210)),
    # ---- 茯苓SP（高阶医护：投瓶群体治疗+全属性增伤）----
    dict(uid="fuling_sp", name="茯苓SP", is_sp=True, sp_of="fuling", base="fuling",
         desc="战地药剂调配。每3秒向全场残血友方投掷愈光药瓶：3×3回复120并施加30%全属性增伤8秒；"
              "大招全屏回复280并清除所有负面debuff。SP须种在茯苓上替换。",
         cost=175, cd=10, hp=550, behavior="healer_sp",
         produce=0, produce_iv=0, attack=0, atk_iv=0,
         heal=120, heal_iv=3, heal_buff=0.30, heal_buff_sec=8,
         ult_name="全域圣愈", ult_desc="全屏所有友方瞬间回复280，并清除所有负面debuff。",
         ult=280, ult_cd=28,
         color=(160, 230, 195)),
    # ---- 琮（群体穿透输出）----
    dict(uid="cong",  name="琮",        is_sp=False,
         desc="定点狙手。贯穿弹极快穿透一条直线上的最多3名敌人，大招连射贯穿整行。",
         cost=175, cd=15, hp=380, behavior="pierce",
         produce=0, produce_iv=0, attack=80, atk_iv=2.5,
         ult_name="勘测连射", ult_desc="连射2发贯穿弹，每发100，穿透整行所有敌人。",
         ult=100, ult_cd=10,
         color=(150, 170, 150)),
    # ---- 莱昂纳多（雷电范围输出）----
    dict(uid="leonardo", name="莱昂纳多", is_sp=False,
         desc="干扰者。链式电弧弹跳到附近敌人，大招导棍插地扩散雷暴领域。",
         cost=200, cd=10, hp=420, behavior="chain",
         produce=0, produce_iv=0, attack=60, atk_iv=1.5, range=4,
         chain_targets=3, splash=0.5,
         ult_name="雷暴领域", ult_desc="导棍插入地面，扩散3×5雷电磁场，对范围内所有敌人造成600雷元素伤害。",
         ult=600, ult_cd=30,
         color=(90, 106, 88)),
    # ---- 卡斯珀（水元素·近战范围输出）----
    dict(uid="casper",  name="卡斯珀",     is_sp=False,
         desc="废土前水文监测员。高压水流横扫自身格及前方4格所有敌人，大招暗潮漩涡持续水伤并击退。",
         cost=50, cd=5, hp=520, behavior="water",
         produce=0, produce_iv=0, attack=55, atk_iv=1.8, range=4,
         ult_name="暗潮漩涡", ult_desc="前方4格持续3秒：每段200水伤并击退敌人4格（总600）。",
         ult=200, ult_cd=30,
         color=(80, 150, 200)),
    # ---- 卡斯珀SP（#10 整行穿透型·水元素）----
    dict(uid="casper_sp", name="卡斯珀SP", is_sp=True, sp_of="casper",
         desc="废土水文观测专家。奔流浪涛穿透整行所有敌人80水伤并降低全体抗性30%；大招归墟大潮整行1000水伤并一次性把整行敌人击退至该行最末端。",
         cost=225, cd=7, hp=480, behavior="water",
         produce=0, produce_iv=0, attack=62, atk_iv=1.8, range=0,
         ult_name="归墟大潮", ult_desc="整行所有敌人1000水伤，并一次性把整行敌人击退至该行最末端格子。",
         ult=1000, ult_cd=30,
         color=(60, 150, 230)),
    # ---- 瓦伦丁（#12 狙击型）----
    dict(uid="valentin", name="瓦伦丁",     is_sp=False,
         desc="废土前狩猎向导。定点狙杀全场血量最高的敌人：600物理穿刺瞬间命中；大招战术再部署：每2次攻击额外狙杀一次。",
         cost=300, cd=20, hp=400, behavior="sniper",
         produce=0, produce_iv=0, attack=600, atk_iv=5,
         crit_rate=0.5,
         ult_name="战术再部署", ult_desc="强化15秒：每2次攻击立即额外再狙杀一次（锁定敌人头顶显示十字光标）。",
         ult=0, ult_cd=20,
         color=(120, 90, 60)),
    # ---- 埃利奥特（增伤辅助位）----
    dict(uid="elliott", name="埃利奥特",   is_sp=False,
         desc="废土前地下乐队吉他手。振奋和弦光环常驻提升3×3范围友方攻击力50%，大招暴走独奏进一步爆发。",
         cost=150, cd=15, hp=450, behavior="buffer",
         produce=0, produce_iv=0, attack=0, atk_iv=0,
         ult_name="暴走独奏", ult_desc="3×3范围友方攻击力额外+50%持续8秒，且后续10次攻击附带20点对应元素真实伤害。",
         ult=0, ult_cd=20,
         color=(90, 110, 160)),
    # ---- 赫利俄（#13 增益辅助位）----
    dict(uid="helio", name="赫利俄",     is_sp=False,
         desc="废土能源研究所光学研究员。聚能棱镜：对正前方一格友方常驻提升80%暴击率与100%爆伤（自身离场即消失）；大招恒光刻印永久赋予100%攻速与50%抗性穿透。",
         cost=450, cd=22, hp=380, behavior="helio",
         produce=0, produce_iv=0, attack=0, atk_iv=0,
         ult_name="恒光刻印", ult_desc="给正前方一格友方刻印【恒光】：永久获得100%攻速提升与50%抗性穿透（不随自身离场消失，目标阵亡才消失）。",
         ult=0, ult_cd=35,
         color=(245, 180, 90)),
    # ---- 烬（龙裔多系异变格斗者·基础常态）----
    dict(uid="rog", name="烬",   is_sp=False,
         desc="龙裔多系异变格斗者。横斩扫荡：对自身前方2格×当前行上下两行的2×3矩形内所有敌人造成50物理劈砍伤害。",
         cost=200, cd=8, hp=550, behavior="rog",
         produce=0, produce_iv=0, attack=50, atk_iv=1.4, range=2, rows=3,
         ult_name="—", ult_desc="无大招。", ult=0, ult_cd=0,
         color=(110, 100, 120)),
    # ---- 烬SP（三元素可变形态）----
    dict(uid="rog_sp", name="烬·SP",  is_sp=True, sp_of="rog",
         desc="三元素可变形态：按空格键切换火/冰/毒形态，2×3横扫替换为对应元素伤害；普攻命中50%触发三行裂斩（自身行±1行整行元素伤害）。",
         cost=400, cd=15, hp=650, behavior="rog",
         produce=0, produce_iv=0, attack=100, atk_iv=1.4, range=2, rows=3,
         ult_name="—", ult_desc="无大招；空格键切换火/冰/毒形态。", ult=0, ult_cd=0,
         color=(150, 110, 80)),
    # ---- 沫（一次性·能源增益位）：部署后4秒持续供能300点，结束自动撤离 ----
    dict(uid="mo", name="沫",   is_sp=False,
         desc="能源拾荒少女。部署落地瞬间启动储能罐，持续4秒产出总计300点能源；期间若被击杀则提前终止供能并撤离；能力结束能量核心烧尽自动撤离。",
         cost=0, cd=20, hp=150, behavior="mo",
         produce=0, produce_iv=0, attack=0, atk_iv=0,
         life_time=4, energy_total=300,          # 存活4秒，总计产出300能量（一次性）
         ult_name="—", ult_desc="无大招（一次性供能单位）。", ult=0, ult_cd=0,
         color=(120, 170, 190)),
    # ---- 雷纳（一次性·全屏爆破位）：部署0.8秒后引爆全场，随后撤离 ----
    dict(uid="rena", name="雷纳", is_sp=False,
         desc="爆破工程师。部署完成0.8秒后引爆全部炸药，对场上所有敌人造成1800爆炸伤害（无视防具防御），引爆后爆破装备损毁自动撤离；引爆前被击杀则爆炸取消。",
         cost=125, cd=20, hp=200, behavior="rena",
         produce=0, produce_iv=0, attack=0, atk_iv=0,
         life_time=0.8, boom_dmg=1800,           # 0.8秒后引爆，全场1800爆炸伤害（一次性）
         ult_name="—", ult_desc="无大招（一次性爆破单位）。", ult=0, ult_cd=0,
         color=(200, 110, 90)),
]

# ============================================================================
# 三、怪物数据区
# ============================================================================
# 【说明】每条字典定义一种怪物：
#   name / desc : 图鉴显示
#   hp / speed  : 生命、移动速度（行动系统里 speed 越大行动越快）
#   atk         : 对单位/基地的啃咬伤害
#   color       : 绘制颜色
#   【后续新增怪物】同样复制一份字典即可。
# 【相对数值换算】用户设定基准：拾荒者 血100/移速1/攻10。
#         换算到本游戏实际数值：血=相对×1.2，移速=相对×0.6，攻击=相对×0.04。
#         （与旧版拾荒者 120血/0.6速/0.4攻 保持一致标尺）
MONSTERS = [
    dict(uid="m_walker", name="废土拾荒者", desc="最常见的废土怪物，行动缓慢但成群出现。",
         hp=260, speed=0.6, atk=30, atk_iv=60, color=(60, 55, 50), defense=2),
    dict(uid="m_child",  name="尘窟窜童",   desc="瘦小迅捷的变异孩童。夯骨巨汉血量过半时会从沙土裂缝钻出，冲到前排偷袭。",
         hp=140, speed=0.9, atk=22, atk_iv=60, color=(110, 100, 90), w=24, h=32),
    dict(uid="m_dog",    name="变异犬",     desc="体型极小的变异禽类，批量刷新；受击会短暂爆发加速冲刺，分散多路骚扰。",
         hp=80, speed=1.5, atk=15, atk_iv=60, color=(90, 60, 45), w=18, h=22, hit_boost=True),
    dict(uid="m_shield", name="混凝土盾手", desc="铁丝捆着混凝土墙块当盾。混凝土只挡正面直线攻击，侧面/斜向可直击本体；盾碎后变拾荒者。",
         hp=300, speed=0.6, atk=30, atk_iv=60, color=(70, 66, 58),
         armor=280, armor_type="shield", break_to="m_walker"),
    dict(uid="m_tank",   name="锈蚀气瓶兵", desc="胸口绑着高压气瓶，全方向攻击先打气瓶；气瓶打爆会对身前一格植物溅射伤害，然后变拾荒者。",
         hp=320, speed=0.6, atk=30, atk_iv=60, color=(55, 62, 60),
         armor=560, armor_type="tank", break_to="m_walker", boom=6),
    dict(uid="m_hulk",   name="夯骨巨汉",   desc="两米高的重度辐射巨人，血量高移速慢；钢筋一击直接摧毁防御单位，血量过半踩踏大地召唤尘窟窜童。",
         hp=1500, speed=0.3, atk=999, atk_iv=60, shatter=True, color=(48, 44, 52),
         w=44, h=56, summon="m_child", summon_num=2, defense=15, resist=0.15),
    dict(uid="m_sprint", name="残骸冲刺者", desc="轻量化金属碎片护甲。护甲完好时高速冲刺，受击护甲脱落移速骤降；护甲破碎后变拾荒者。",
         hp=280, speed=0.84, speed_break=0.48, atk=30, atk_iv=60, color=(80, 74, 62),
         armor=600, armor_type="scrap", break_to="m_walker"),
    dict(uid="m_end",    name="末日终结者", desc="测试关卡的巨型怪物，血量极高、移动极其缓慢，用来测试输出。",
         hp=25000, speed=0.2, atk=50, atk_iv=60, color=(35, 40, 60), giant=True,
         defense=40, resist=0.15),
    # ===== 第4关起加入的新怪物（机制多样：践踏/远程诅咒/酸蚀/跳跃/冰爆/召唤） =====
    dict(uid="m_wolf", name="铁脊豺狼", desc="精英掠食者，灰黑色狼形，高速高攻，成群来袭时非常致命。",
         hp=560, speed=1.1, atk=50, color=(85, 90, 100), w=36, h=34, atk_iv=60),
    dict(uid="m_brute", name="辐射蛮牛", desc="重装冲撞型怪物。每次攻击践踏自身与身后一格，同时碾伤两个防御单位。",
         hp=760, speed=0.55, atk=42, color=(92, 74, 58), w=46, h=42, atk_iv=60, stampede=True),
    dict(uid="m_hexer", name="污染术士", desc="远程诅咒者。走到防线前停下，每隔数秒对随机防御单位施放腐蚀诅咒，使其持续掉血。",
         hp=360, speed=0.6, atk=0, color=(100, 62, 96), w=32, h=42,
         ranged=True, r_atk_iv=60, r_dmg=25, r_dot=3, r_dot_len=90),
    dict(uid="m_spitter", name="酸液喷射者", desc="远程酸液怪。停下后喷吐强酸，对防御单位造成无视防御的真实伤害并留下腐蚀。",
         hp=320, speed=0.65, atk=0, color=(70, 105, 62), w=34, h=36,
         ranged=True, r_atk_iv=60, r_dmg=30, r_dot=3, r_dot_len=150, true_dmg=True),
    dict(uid="m_raptor", name="裂爪迅猛龙", desc="快速掠食者，每5秒纵身一跃跳过2格防线，直接从防线上方越过突袭后排。",
         hp=460, speed=1.25, atk=40, color=(88, 78, 56), w=36, h=34, atk_iv=60,
         jump_cd=300, jump_dist=170),
    dict(uid="m_frost", name="霜皮丧尸", desc="覆盖冰甲的丧尸，冰元素抗性极高，行动缓慢。被击杀时冰甲爆裂，对周围防御单位造成冰霜溅射。",
         hp=820, speed=0.45, atk=36, color=(70, 95, 130), w=34, h=44, atk_iv=60,
         resist={"ice": 0.5, "physical": 0.1}, death_boom=35, death_boom_element="ice"),
    dict(uid="m_king", name="废土尸王", desc="尸群首领，浑身缠着锈铁与白骨。防御与元素抗性极高，重击前排；被击败时尸气爆发，召唤4只拾荒者。",
         hp=2400, speed=0.3, atk=60, color=(58, 52, 62), w=46, h=58, atk_iv=60,
         defense=40, resist=0.25, death_summon="m_walker", death_summon_num=4),
    # ===== 高难关强力怪物（数千血级，第9关起登场） =====
    dict(uid="m_colossus", name="装甲巨像", desc="报废机甲改造的重装巨像，浑身焊满装甲板。高防高血，重拳每击砸裂防线。",
         hp=3800, speed=0.2, atk=70, color=(70, 80, 95), w=52, h=60, atk_iv=60,
         defense=38, resist=0.2),
    dict(uid="m_queen", name="尸巢母体", desc="肿胀的变异母体，持续孵化尘窟窜童。血量过半与阵亡时都会大批破土召唤。",
         hp=3200, speed=0.35, atk=40, color=(95, 55, 60), w=48, h=56, atk_iv=60,
         summon="m_child", summon_num=4, death_summon="m_child", death_summon_num=3),
    dict(uid="m_tyrant", name="废土暴君", desc="辐射变异称霸者，金属骨甲覆身。数千血量，重击高额伤害，普通防线在它面前如纸。",
         hp=5200, speed=0.25, atk=80, color=(52, 46, 58), w=48, h=62, atk_iv=60,
         defense=42, resist=0.25),
    dict(uid="m_leviathan", name="辐射利维坦", desc="盘踞废土深渊的巨型辐射巨兽，横跨所有战线。八千血量、极高防御，一旦放行将碾碎整条防线。",
         hp=8500, speed=0.15, atk=90, color=(40, 55, 60), w=60, h=70, atk_iv=60,
         giant=True, defense=30, resist=0.3),
    dict(uid="m_dummy",  name="测试沙包",   desc="DPS试炼场的巨型沙包：超厚血、不移动不攻击，用来统计总伤害与DPS。",
         hp=500000, speed=0, atk=0, color=(168, 138, 88), w=46, h=58,
         defense=0, resist=0, dummy=True),
]

# ============================================================================
# 四、关卡数据区
# ============================================================================
# 【说明】每关定义若干波（wave），每波 spawn_monster 是要生成的怪物uid列表，
#         wave_gap 是两波之间的间隔（帧）。
#         start_energy 是本关开局的初始能量。
#         【能源机制】能量不随时间自动增长：必须靠里昂产出能源球，鼠标移到球上拾取；
#         里昂大招也会直接产出能源。
#         波内怪物间隔由战斗场景统一控制：每波第一只开局10秒后出现，
#         之后每只随机间隔3~10秒，难度越高间隔越短（出怪频率越快，总量不变）。
#         （旧字段 spawn_gap 已不使用，仅保留兼容）
#         【后续新增关卡】在 LEVELS 里加一个条目即可。
LEVELS = [
    # 第1关：教学关，拾荒者 + 变异犬
    dict(level=1, name="第1关 · 初见废土", start_energy=200,
         waves=[
             dict(spawn=["m_walker","m_walker","m_walker"], spawn_gap=60, wave_gap=120),
             dict(spawn=["m_walker","m_dog","m_dog","m_walker"], spawn_gap=50, wave_gap=150),
         ]),
    # 第2关：加入混凝土盾手与残骸冲刺者
    dict(level=2, name="第2关 · 废土侵攻", start_energy=250,
         waves=[
             dict(spawn=["m_walker","m_shield","m_walker"], spawn_gap=50, wave_gap=120),
             dict(spawn=["m_dog","m_sprint","m_shield","m_dog"], spawn_gap=45, wave_gap=150),
             dict(spawn=["m_walker","m_sprint","m_shield","m_dog","m_walker"], spawn_gap=40, wave_gap=0),
         ]),
    # 第3关：加入锈蚀气瓶兵与夯骨巨汉（巨汉血量过半召唤尘窟窜童）
    dict(level=3, name="第3关 · 铁骨狂潮", start_energy=300,
         waves=[
             dict(spawn=["m_tank","m_walker","m_shield"], spawn_gap=60, wave_gap=150),
             dict(spawn=["m_dog","m_tank","m_sprint","m_hulk"], spawn_gap=50, wave_gap=150),
             dict(spawn=["m_hulk","m_sprint","m_tank","m_shield","m_dog","m_walker","m_tank"], spawn_gap=45, wave_gap=0),
         ]),
    # 第4关：沙尘暴规则（所有怪物移速+15%）——铁脊豺狼 / 辐射蛮牛登场
    dict(level=4, name="第4关 · 尘暴荒原", start_energy=300,
         rules=["沙尘暴"], rule_desc="沙尘暴：所有怪物移速+15%",
         waves=[
             dict(spawn=["m_walker","m_wolf","m_walker"], spawn_gap=55, wave_gap=130),
             dict(spawn=["m_brute","m_wolf","m_dog","m_walker"], spawn_gap=48, wave_gap=150),
             dict(spawn=["m_wolf","m_brute","m_walker","m_walker","m_wolf","m_dog"], spawn_gap=42, wave_gap=0),
         ]),
    # 第5关：铁雨空降规则（每15秒随机空降2只变异犬）——污染术士 / 酸液喷射者 / 裂爪迅猛龙登场
    dict(level=5, name="第5关 · 幽魂地铁", start_energy=320,
         rules=["铁雨空降"], rule_desc="铁雨空降：每15秒随机空降2只变异犬",
         waves=[
             dict(spawn=["m_hexer","m_walker","m_spitter"], spawn_gap=55, wave_gap=140),
             dict(spawn=["m_raptor","m_hexer","m_dog","m_spitter"], spawn_gap=48, wave_gap=150),
             dict(spawn=["m_raptor","m_raptor","m_hexer","m_spitter","m_walker","m_walker"], spawn_gap=42, wave_gap=0),
         ]),
    # 第6关：辐射潮汐规则（每20秒所有怪物恢复5%生命）——霜皮丧尸（冰抗+死亡冰爆）登场
    dict(level=6, name="第6关 · 霜冻哨站", start_energy=340,
         rules=["辐射潮汐"], rule_desc="辐射潮汐：每20秒所有怪物恢复5%生命",
         waves=[
             dict(spawn=["m_frost","m_walker","m_shield"], spawn_gap=55, wave_gap=140),
             dict(spawn=["m_frost","m_frost","m_walker","m_hulk"], spawn_gap=50, wave_gap=150),
             dict(spawn=["m_frost","m_tank","m_frost","m_shield","m_walker","m_walker"], spawn_gap=44, wave_gap=0),
         ]),
    # 第7关：精英血脉规则（本关所有怪物血量×1.5、移速×0.9）——全精英速攻
    dict(level=7, name="第7关 · 荒野猎杀", start_energy=350,
         rules=["精英血脉"], rule_desc="精英血脉：本关怪物血量×1.5、移速×0.9",
         waves=[
             dict(spawn=["m_raptor","m_wolf","m_dog"], spawn_gap=50, wave_gap=130),
             dict(spawn=["m_brute","m_raptor","m_wolf","m_dog"], spawn_gap=45, wave_gap=150),
             dict(spawn=["m_raptor","m_wolf","m_brute","m_raptor","m_dog","m_wolf"], spawn_gap=40, wave_gap=0),
         ]),
    # 第8关：boss关，铁雨空降+辐射潮汐双规则——废土尸王坐镇
    dict(level=8, name="第8关 · 尸王巢穴", start_energy=400,
         rules=["铁雨空降", "辐射潮汐"], rule_desc="铁雨空降 + 辐射潮汐：怪物持续增援并回血",
         waves=[
             dict(spawn=["m_king","m_walker","m_walker","m_shield","m_shield"], spawn_gap=60, wave_gap=160),
             dict(spawn=["m_hexer","m_spitter","m_frost","m_tank","m_walker"], spawn_gap=48, wave_gap=160),
             dict(spawn=["m_brute","m_raptor","m_wolf","m_dog","m_dog","m_walker"], spawn_gap=42, wave_gap=0),
         ]),
    # 第9关：装甲要塞——数千血强怪登场（装甲巨像/废土暴君/尸巢母体），精英血脉强化
    dict(level=9, name="第9关 · 装甲要塞", start_energy=450,
         rules=["精英血脉"], rule_desc="精英血脉：本关怪物血量×2、移速×0.85；数千血的装甲巨像与暴君压境",
         waves=[
             dict(spawn=["m_colossus","m_walker","m_walker","m_shield","m_shield"], spawn_gap=60, wave_gap=160),
             dict(spawn=["m_tyrant","m_queen","m_wolf","m_frost","m_tank"], spawn_gap=50, wave_gap=160),
             dict(spawn=["m_colossus","m_tyrant","m_queen","m_brute","m_raptor","m_hexer"], spawn_gap=45, wave_gap=0),
         ]),
    # 第10关：利维坦之渊——巨型辐射利维坦横跨所有战线，配合暴君与母体
    dict(level=10, name="第10关 · 利维坦之渊", start_energy=500,
         rules=["辐射潮汐", "精英血脉"], rule_desc="辐射潮汐 + 精英血脉：怪物持续回血且血量×2；利维坦巨兽压阵",
         waves=[
             dict(spawn=["m_leviathan","m_colossus","m_walker","m_walker"], spawn_gap=65, wave_gap=170),
             dict(spawn=["m_queen","m_tyrant","m_colossus","m_frost","m_spitter"], spawn_gap=50, wave_gap=170),
             dict(spawn=["m_leviathan","m_tyrant","m_queen","m_colossus","m_brute","m_wolf"], spawn_gap=45, wave_gap=0),
         ]),
]

# 测试关：末日终结者（25000血巨型怪，用于测试输出/大招）。独立于常规关卡，
# 在选关界面与 DPS 试炼场同排作为特殊入口（不占用关卡编号）。
TEST_LEVEL = dict(level=0, name="测试关 · 末日终结者", start_energy=500,
                  waves=[dict(spawn=["m_end"], spawn_gap=0, wave_gap=0)])


# ============================================================================
# 五、全局游戏状态区（跨场景共享的数据）
# ============================================================================
# 【说明】Game 对象在程序启动时创建，贯穿所有场景，保存玩家设置、
#         当前关卡、选好的卡牌等。任何场景都能通过 game.xxx 读取/修改。
# 【难度配置】倍率基准 = 简单（当前数值）：出怪频率×1、怪物血量×1。
#   普通 = 出怪频率×2（间隔缩短一半）、怪物血量×2；困难 = 出怪频率×5、怪物血量×2。
#   注意：难度只加快单位时间出怪频率（总数不变），不出怪量×倍率复制。
DIFF_CONFIG = {
    "简单": dict(spawn_mult=1, hp_mult=1.0),
    "普通": dict(spawn_mult=2, hp_mult=2.0),
    "困难": dict(spawn_mult=5, hp_mult=2.0),
}

class Game:
    def __init__(self):
        # ---- 设置项 ----
        self.music_on = True          # 音乐开关
        self.volume = 70              # 音量 0~100（预留接口）
        self.difficulty = "简单"      # 难度：简单 / 普通 / 困难（简单=当前基准）
        self.cheat = False            # 测试模式（测试用：无限能量）
        self.dps_mode = False         # DPS试炼场标记（关卡选择里进入，一次性消费）
        # ---- 无尽模式状态 ----
        self.endless_mode = False         # 无尽模式标记
        self.endless_stage = 1            # 当前无尽关卡（从1开始，无限递增）
        self.endless_keep_units = []      # 跨关保留的单位：(uid, cx, cy, hp比例, 大招冷却)
        self.endless_energy = 0           # 跨关保留的能量
        # ---- 流程状态 ----
        self.selected_level = None    # 选中的关卡下标（对应 LEVELS）
        self.selected_cards = []      # 战前选好的卡牌（uid 列表，最多10）
        # ---- 场景切换 ----
        self.scene = "load"           # 当前场景名（见主循环场景字典）
        # ---- 结果回传 ----
        self.result_msg = ""          # 战斗结束提示（胜利/失败）

    def energy_value(self, n):
        """按难度调整能源球价值：简单×1.3，困难×0.7，普通原值。"""
        if self.difficulty == "简单":
            return int(n * 1.3)
        if self.difficulty == "困难":
            return int(n * 0.7)
        return n

    def reset_endless(self):
        """重置无尽模式状态（进入无尽/结束/中途退出时调用）。"""
        self.endless_mode = False
        self.endless_stage = 1
        self.endless_keep_units = []
        self.endless_energy = 0

    # ---- 无尽模式持久化存档：关闭程序后也能恢复阵容与关卡进度 ----
    def endless_save_path(self):
        """无尽存档文件路径（与主程序同目录，save.json）。"""
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "save.json")

    def save_endless_snapshot(self):
        """把当前无尽关卡、能量、阵容（含烬SP形态、恒光刻印）写入 save.json，重启后可恢复。"""
        data = {
            "endless_stage": self.endless_stage,
            "endless_energy": self.endless_energy,
            "units": [{"uid": u, "x": x, "y": y, "ratio": r, "ult_cd": c,
                       "rog_form": f, "eternal_seal": e}
                      for u, x, y, r, c, f, e in self.endless_keep_units],
        }
        try:
            with open(self.endless_save_path(), "w", encoding="utf-8") as fp:
                json.dump(data, fp, ensure_ascii=False)
        except Exception:
            pass

    def load_endless_snapshot(self):
        """从 save.json 恢复无尽状态（关卡/能量/阵容）；成功返回 True，无存档返回 False。"""
        try:
            with open(self.endless_save_path(), "r", encoding="utf-8") as fp:
                data = json.load(fp)
            self.endless_stage = max(1, int(data.get("endless_stage", 1)))
            self.endless_energy = int(data.get("endless_energy", 0))
            self.endless_keep_units = [
                (u.get("uid"), u.get("x", 0), u.get("y", 0),
                 u.get("ratio", 1.0), u.get("ult_cd", 0),
                 u.get("rog_form", 0), u.get("eternal_seal", False))
                for u in data.get("units", [])]
            self.endless_mode = True
            return True
        except Exception:
            return False

    def clear_endless_snapshot(self):
        """清除无尽存档（一局失败结束 / 明确新开一局时调用）。"""
        try:
            p = self.endless_save_path()
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

# ============================================================================
# 六、UI 工具区：按钮、开关等通用控件
# ============================================================================
# 【说明】这些控件被多个界面复用。新增界面直接用 Button 即可。
class Button:
    """通用矩形按钮：可设置文字、位置、大小、点击回调。"""
    def __init__(self, x, y, w, h, text, callback=None, font=None):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.callback = callback
        self.font = font if font else pygame.font.SysFont("simhei", 22)
        self.hover = False

    def handle_event(self, event):
        """鼠标移动高亮、鼠标左键点击触发回调。"""
        if event.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos) and self.callback:
                self.callback()

    def draw(self, screen):
        color = COLOR_BUTTON_H if self.hover else COLOR_BUTTON
        pygame.draw.rect(screen, color, self.rect, border_radius=6)
        pygame.draw.rect(screen, COLOR_GRID, self.rect, 2, border_radius=6)
        img = self.font.render(self.text, True, COLOR_TEXT)
        screen.blit(img, (self.rect.centerx - img.get_width()//2,
                          self.rect.centery - img.get_height()//2))

_FONT_CACHE = {}                     # 字体缓存：按 size 缓存 Font 对象，避免每帧重复创建
def make_font(size):
    """快捷创建中文字体（带全局缓存，避免每帧重复创建 Font 对象——性能关键）。"""
    f = _FONT_CACHE.get(size)
    if f is None:
        f = pygame.font.SysFont("simhei", size)
        _FONT_CACHE[size] = f
    return f

def draw_first_col_x(screen, x, y):
    """在最右列（第一格，禁止部署的怪物出生区）格子上画一个灰色叉叉，提示玩家不能种。"""
    m = 16                                   # 叉与格边距
    col = (130, 132, 140)                    # 灰色
    pygame.draw.line(screen, col, (x + m, y + m), (x + CELL_W - m, y + CELL_H - m), 2)
    pygame.draw.line(screen, col, (x + CELL_W - m, y + m), (x + m, y + CELL_H - m), 2)

def draw_hover_panel(screen, cx, cy, title, items,
                     title_border=(120, 128, 140),
                     item_bg=(15, 25, 35), item_border=(90, 150, 210)):
    """绘制悬停信息面板（角色增益 / 怪物减益共用，减少重复代码）：
       居中于 (cx, cy) 上方先画一条半透明标题标签，再向下逐行排列多个小标签。
       items: [(文字, 渲染颜色)]，颜色即小标签文字色。"""
    nm = make_font(16).render(title, True, COLOR_WHITE)
    tag = pygame.Surface((nm.get_width() + 16, 24), pygame.SRCALPHA)
    tag.fill((15, 18, 22, 210))
    pygame.draw.rect(tag, title_border, tag.get_rect(), 1, border_radius=4)
    screen.blit(tag, (cx - nm.get_width() // 2 - 8, cy - 58))
    screen.blit(nm, (cx - nm.get_width() // 2, cy - 55))
    yy = cy - 58 + 28
    for itxt, icol in items:
        gt = make_font(14).render(itxt, True, icol)
        gtag = pygame.Surface((gt.get_width() + 12, 20), pygame.SRCALPHA)
        gtag.fill((*item_bg, 200))
        pygame.draw.rect(gtag, item_border, gtag.get_rect(), 1, border_radius=3)
        screen.blit(gtag, (cx - gt.get_width() // 2 - 6, yy))
        screen.blit(gt, (cx - gt.get_width() // 2, yy + 2))
        yy += 22

# ============================================================================
# 六.5 伤害结算系统（完整伤害公式）
# ============================================================================
# 【说明】所有伤害（弹丸/大招/持续伤害/怪物攻击）统一走 DamageSystem.calc 结算。
#   完整公式（顺序：攻击 → 减防御 → 增伤/减伤 → 抗性 → 暴击）：
#     最终伤害 = max(保底,
#                   ( [攻击×(1+攻加%)+固定攻] × 倍率 - max(0, 防×(1-减防%)-穿透) )
#                   × (1+增伤%-减伤%) × (1-(抗%-减抗%)) × 暴击系数 )
#   规则：
#     · 有效防御 D = max(0, 防×(1-减防%)-穿透)，最低为 0，防止负防御
#     · 增伤区 E = max(0.1, 1+增伤%-减伤%)，下限 0.1，防止伤害被压到 0 或负数
#     · 抗性区 R = max(0.1, 1-(抗%-减抗%))，下限 0.1
#     · 保底伤害必加：最终伤害至少 = 基础攻击×K（K=保底系数），否则高防单位完全打不动
#     · 同类型加成先加算（攻加%叠加、增伤%叠加、减防%叠加、减抗%叠加），
#       不同类型（攻击→防御→增伤→抗性→暴击）乘算
#     · 调平衡主要动 K（保底系数）和各乘区上限（E/R 下限）
#     · 角色基础暴击率 20%、基础暴击伤害加成 50%（辅助角色可再加暴击/爆伤）
#     · 怪物也有自己的防御值(defense)与抗性(resist，支持按元素区分)
class DamageSystem:
    """统一伤害结算系统。"""
    BASE_CRIT_RATE = 0.20    # 基础暴击率
    BASE_CRIT_DMG  = 0.50    # 基础暴击伤害加成（暴击时 ×1.5）
    K = 0.15                 # 保底系数：最终伤害至少 = 基础攻击×K（至少1点），调平衡动这里
    E_MIN = 0.1              # 增伤区下限
    R_MIN = 0.1              # 抗性区下限

    @staticmethod
    def calc(base_atk, element="physical",
             atk_pct=0.0, flat_atk=0.0, mult=1.0,
             defense=0.0, armor_reduce=0.0, pierce=0.0,
             dmg_inc=0.0, dmg_reduce=0.0,
             resist=0.0, resist_reduce=0.0,
             crit_rate=None, crit_dmg=None, use_floor=True):
        """按完整公式结算一次伤害。
        参数：
          base_atk        基础攻击力（普攻=attack，大招/持续伤害=对应数值）
          element         元素类型 physical/fire/ice/bolt（决定受击方按元素取抗性）
          atk_pct         攻击力百分比加成（攻加%）
          flat_atk        固定攻击力加成
          mult            技能倍率（普攻1.0，溅射/多段用）
          defense         受击方防御值（怪物防御）
          armor_reduce    减防%（攻击方施加，多来源加算）
          pierce          穿透（直接抵扣有效防御）
          dmg_inc         增伤%（攻击方，多来源加算）
          dmg_reduce      减伤%（受击方，多来源加算）
          resist          受击方抗性%（怪物抗性，可按元素）
          resist_reduce   减抗%（攻击方施加，多来源加算）
          crit_rate       暴击率（默认基础20%）
          crit_dmg        暴击伤害加成（默认基础50%）
        返回：(实际伤害值, 是否暴击)"""
        # 攻击区：攻击×(1+攻加%) + 固定攻
        atk = base_atk * (1 + atk_pct) + flat_atk
        # 减防御区：有效防御最低为0（防止负防御）
        d = max(0.0, defense * (1 - armor_reduce) - pierce)
        # 增伤/减伤区：下限 E_MIN（同类型加算：多个增伤/减伤先相加）
        e = max(DamageSystem.E_MIN, 1 + dmg_inc - dmg_reduce)
        # 抗性区：下限 R_MIN（减抗直接抵扣抗性）
        r = max(DamageSystem.R_MIN, 1 - (resist - resist_reduce))
        # 暴击区：基础暴击率20%，暴击时伤害×(1+爆伤加成)
        cr = DamageSystem.BASE_CRIT_RATE if crit_rate is None else crit_rate
        cd = DamageSystem.BASE_CRIT_DMG if crit_dmg is None else crit_dmg
        crit = random.random() < cr
        crit_mult = (1 + cd) if crit else 1.0
        # 保底伤害：最终至少 = 基础攻击×K（至少1点），避免高防单位完全打不动。
        # use_floor=False 时不取整、不保底（怪物攻击用：小数值攻击力保留浮点，避免被保底放大）
        raw = (atk * mult - d) * e * r * crit_mult
        if use_floor:
            floor = max(1, int(base_atk * DamageSystem.K))
            return (max(floor, int(round(raw))), crit)
        return (raw, crit)

    @staticmethod
    def text_color(element, epic=False, crit=False):
        """伤害数字配色：SP大招弹爆炸橙，其余按元素色；
           暴击不改颜色，只由调用处放大字号区分。"""
        if epic:
            return DAMAGE_COLOR_BOOM
        return {"physical": DAMAGE_COLOR_PHYS, "fire": DAMAGE_COLOR_FIRE,
                "ice": DAMAGE_COLOR_ICE, "bolt": DAMAGE_COLOR_BOLT,
                "water": DAMAGE_COLOR_WATER, "poison": DAMAGE_COLOR_POISON}.get(element, DAMAGE_COLOR_PHYS)


def apply_elemental_hit(element, m, base_atk, monsters):
    """元素命中后的【状态附加】与【元素反应】（每次攻击动作命中时调用）。
    参数：
      element   本次攻击的元素类型 physical/fire/ice/bolt/water
      m         被击中的怪物（可能已死亡，状态附加仍执行但调用方负责清理）
      base_atk  攻击方基础攻击力（感电/爆炸按此比例折算）
      monsters  当前怪物列表（感电/爆炸需要扫描范围目标）
    返回 (bonus_dmg_inc, extras)：
      bonus_dmg_inc  本次攻击结算时额外叠加的增伤%（+0.25/+0.5，同类型与攻击方增伤加算）
      extras         [(目标怪, 伤害, 元素, 标签)] 感电/爆炸额外伤害，由调用方另行结算

    状态规则：
      水伤命中 -> 潮湿5秒；水攻灼烧：解除灼烧+本次伤害+25%；水攻寒冷：5%概率冻结2秒
      冰伤命中 -> 寒冷5秒（移速/攻速-40%、物理/冰抗-20%，冻结状态下也同时获得寒冷）；
                  冰攻潮湿：5%概率冻结2秒；冰攻灼烧：解除灼烧+本次伤害+50%
      火伤命中 -> 灼烧由各火系角色自行附加（数值不同）；火攻寒冷/冻结：取消状态+本次+50%；
                  火攻潮湿：解除潮湿+本次+25%（接下来1秒内伤害提升，简化为一击生效）
      雷伤命中 -> 麻痹0.4秒；雷攻潮湿：3×3范围内所有潮湿敌人额外受一次感电=自身攻25%；
                  雷攻寒冷：麻痹延长至0.6秒；雷攻冻结：本次伤害+25%；
                  雷攻灼烧：同一格内敌人额外受一次爆炸=自身攻50%（爆炸无视防具防御）
      真实伤害：不参与任何反应，数值是多少就是多少（由调用方单独附加）。"""
    # 生成保护：第一格怪物完全不受状态附加、不参与元素反应（直到走到第二格解除保护）
    if getattr(m, "spawn_protect", False):
        return 0.0, []
    bonus = 0.0
    extras = []
    # ---- 基础状态附加 ----
    if element == "water":
        m.wet_timer = 5 * FPS
    elif element == "ice":
        m.cold_timer = max(m.cold_timer, 5 * FPS)
    elif element == "bolt":
        m.paralyze_timer = max(m.paralyze_timer, int(0.4 * FPS))
    # fire：灼烧由火系攻击者（伊格尼斯）显式附加，数值各角色不同
    # ---- 元素反应 ----
    if element == "water":
        if m.burn_timer > 0:                        # 水攻灼烧：解除灼烧，伤害+25%
            m.burn_timer = 0
            m.burn_dmg = 0
            bonus += 0.25
        if m.cold_timer > 0 and random.random() < 0.05:      # 水攻寒冷：5%冻结2秒
            m.freeze_timer = max(m.freeze_timer, 2 * FPS)
    elif element == "ice":
        if m.wet_timer > 0 and random.random() < 0.05:       # 冰攻潮湿：5%冻结2秒
            m.freeze_timer = max(m.freeze_timer, 2 * FPS)
        if m.burn_timer > 0:                        # 冰攻灼烧：解除灼烧，伤害+50%
            m.burn_timer = 0
            m.burn_dmg = 0
            bonus += 0.5
    elif element == "fire":
        if m.cold_timer > 0 or m.freeze_timer > 0:  # 火攻寒冷/冻结：取消状态，伤害+50%
            m.cold_timer = 0
            if m.freeze_timer > 0:
                m.freeze_timer = 0
                m.frost_timer = 0
            bonus += 0.5
        elif m.wet_timer > 0:                       # 火攻潮湿：解除潮湿，伤害+25%
            m.wet_timer = 0
            bonus += 0.25
    elif element == "bolt":
        if m.wet_timer > 0:                         # 雷攻潮湿：3×3内潮湿敌人感电（自身攻25%）
            for o in monsters:
                if o.hp > 0 and not getattr(o, "spawn_protect", False) \
                   and o.wet_timer > 0 and abs(o.x - m.x) < CELL_W * 1.5 and abs(o.y - m.y) < CELL_H * 1.5:
                    extras.append((o, max(1, int(base_atk * 0.25)), "bolt", "感电"))
        if m.cold_timer > 0:                        # 雷攻寒冷：麻痹0.6秒
            m.paralyze_timer = max(m.paralyze_timer, int(0.6 * FPS))
        if m.freeze_timer > 0:                      # 雷攻冻结：本次伤害+25%
            bonus += 0.25
        if m.burn_timer > 0:                        # 雷攻灼烧：同格爆炸（自身攻50%，无视防具）
            for o in monsters:
                if o.hp > 0 and not getattr(o, "spawn_protect", False) \
                   and abs(o.y - m.y) < CELL_H * 0.7 and abs(o.x - m.x) < CELL_W * 0.7:
                    extras.append((o, max(1, int(base_atk * 0.5)), "explosive", "爆炸"))
    return bonus, extras


def apply_sp_ice_splash(hit_m, b, monsters, scene):
    """白夜SP白银冰破弹：命中 hit_m 后，
       1) 始终在【第一个被击中的敌人】身上爆开一个寒霜扩散特效（标识这是带溅射的白银冰破弹，
          每次命中稳定显示，不会时有时无）；
       2) 对其 3×3 范围内其它敌人额外溅射一次冰伤（溅射伤害 = 弹丸伤害 × sp_splash，含冰元素反应）。"""
    if not getattr(b, "sp_splash", None):
        return
    scene.fx.append(IceSplashFx(hit_m.x, hit_m.y, big=True))   # 命中敌人身上发出一个溅射特效
    sx = b.damage * b.sp_splash
    for t in monsters[:]:
        if t is hit_m or t.hp <= 0 or getattr(t, "spawn_protect", False):
            continue
        # 圆形溅射判定：以命中目标为圆心，半径 1.5 格（圆形覆盖到约 3×3 格区域，非精确方块）
        #   x/y 分别按格宽/格高归一化后求欧氏距离；巨型怪横跨全行视为命中
        dx = (t.x - hit_m.x) / CELL_W
        dy = (t.y - hit_m.y) / CELL_H
        if t.giant or math.hypot(dx, dy) <= 1.5:
            t_pre_resist = t.resist_of("ice")   # 溅射目标命中前抗性快照（避免本发附加的寒冷影响本次溅射）
            bonus, extras = apply_elemental_hit("ice", t, sx, monsters)
            # 白夜SP白银冰破弹自带溅射冻结：命中溅射目标有25%概率冻结2秒
            # （叠加在冰元素反应之上；冻结同时获得寒冷并受冻伤，符合冻结规则）
            if random.random() < 0.25:
                t.freeze_timer = max(t.freeze_timer, 2 * FPS)
                t.cold_timer = max(t.cold_timer, 5 * FPS)
                t.frost_timer = max(t.frost_timer, 2 * FPS)
                t.frost_dmg = max(t.frost_dmg, 50)   # 冻伤50/秒（若已有更高冻伤则保留）
            sdm, _ = DamageSystem.calc(
                base_atk=sx, element="ice",
                defense=t.defense, resist=t_pre_resist,
                atk_pct=b.attrs.get("atk_pct", 0.0), flat_atk=b.attrs.get("flat_atk", 0.0),
                mult=b.attrs.get("mult", 1.0), pierce=b.attrs.get("pierce", 0.0),
                dmg_inc=b.attrs.get("dmg_inc", 0.0) + bonus,
                armor_reduce=b.attrs.get("armor_reduce", 0.0),
                resist_reduce=b.attrs.get("resist_reduce", 0.0),
                crit_rate=b.attrs.get("crit_rate", None), crit_dmg=b.attrs.get("crit_dmg", None))
            t.take_hit(sdm, "aoe")
            scene.fx.append(FloatingText(t.x, t.y - 26, f"-{sdm}", DAMAGE_COLOR_ICE, 14))
            for (tt, ed, el, label) in extras:
                if tt.hp > 0 and tt in monsters:
                    tt.take_hit(ed, "explosive" if label == "爆炸" else "aoe")
                    scene.fx.append(FloatingText(tt.x, tt.y - 26, f"-{ed}", DamageSystem.text_color(el), 14))
                    if tt.hp <= 0:
                        tt.die(scene)
            if t.hp <= 0:
                t.die(scene)


class IceSplashFx:
    """白夜SP白银冰破弹的溅射视觉特效：以命中目标为圆心，向外扩散寒霜环
       + 飞散冰晶粒子 + 中心寒光一闪，短暂淡出。"""
    def __init__(self, x, y, big=False):
        self.x, self.y = x, y
        self.big = big
        self.life = 16

    def update(self):
        self.life -= 1
        return self.life > 0

    def draw(self, screen):
        # 环形冰晶扩散：扩散进度 0~15，环随进度扩大并淡出
        k = 14 - self.life
        r = 8 + k * (2.6 if self.big else 1.4)   # 扩散环半径（big 覆盖约 3×3 的 1.5 格）
        pygame.draw.circle(screen, (150, 215, 255), (self.x, self.y), int(r), 2)   # 寒霜扩散环
        n = 8 if self.big else 5
        for i in range(n):                       # 向外飞散的冰晶粒子（随环旋转扩散）
            a = math.radians(i * (360 // n)) + k * 0.18
            px = self.x + math.cos(a) * r
            py = self.y + math.sin(a) * r
            pygame.draw.circle(screen, (215, 242, 255), (int(px), int(py)), 2)
        pygame.draw.circle(screen, (200, 235, 255), (self.x, self.y),
                           max(2, 6 - self.life // 4))   # 中心寒光一闪


# ============================================================================
# 七、战斗实体区：能源球 / 子弹 / 防御单位(耕地者) / 怪物
# ============================================================================
# 【说明】战斗界面里的所有活动对象都在这一区。每个实体负责自己的
#         绘制、更新和移动。防御单位的“行为”通过数据区 behavior 字段驱动。

# 能量UI文字"能量：N"显示在顶部 (170,16)，文字中心约在此处——能源球自动飞向该点并拾取
ENERGY_UI_X, ENERGY_UI_Y = 215, 30


class EnergyOrb:
    """能源球：里昂产出的资源，自动在1秒内飞向顶部"能量"文字处并自动拾取（无需鼠标点击）。"""
    def __init__(self, x, y, value, land_y):
        self.x, self.y = x, y
        self.x0, self.y0 = x, y
        self.value = value
        self.land_y = land_y
        self.vy = 1.0
        self.landed = False
        self.life = FPS      # 1秒内飞到能量处
        self.phase = 0

    def update(self, game_state, mouse_pos):
        """自动拾取：线性匀速飞向能量UI文字处，1秒后到达并加能量返回 False（移除）。"""
        if self.life > 0:
            k = 1.0 / FPS
            self.x += (ENERGY_UI_X - self.x0) * k
            self.y += (ENERGY_UI_Y - self.y0) * k
            self.life -= 1
        if self.life <= 0:
            self.x, self.y = ENERGY_UI_X, ENERGY_UI_Y
            game_state["scene"].energy += self.value
            return False
        return True

    def draw(self, screen):
        self.phase = (self.phase + 0.1) % 360
        r = 11 + 2 * abs(math.sin(self.phase))
        pygame.draw.circle(screen, (255, 230, 120), (self.x, self.y), r)
        pygame.draw.circle(screen, (255, 210, 60), (self.x, self.y), r - 3)
        pygame.draw.circle(screen, (255, 250, 220), (self.x - r//3, self.y - r//3), 3)


class Bullet:
    """弹丸：远程单位发射的弹丸，直线前进，命中怪物造成伤害。ice=True 为冰弹（白夜），ult=True 为大招弹（凯恩）。"""
    def __init__(self, x, y, damage, speed=12, ice=False, ult=False, epic=False,
                 pierce=False, pierce_max=3, element="physical", attrs=None, sp_splash=None):
        self.x, self.y = x, y
        self.damage = damage
        self.speed = speed
        self.ice = ice
        self.ult = ult
        self.epic = epic   # SP凯恩大招弹：华丽版（更大弹体+旋转光弧+长拖尾+命中爆闪）
        self.pierce = pierce        # 贯穿弹（琮）：命中后不消失，继续穿透下一个敌人
        self.pierce_max = pierce_max
        self.pierce_left = pierce_max
        self.pierce_hit = []        # 贯穿弹已命中的怪物对象引用：防止同一目标被重复穿透伤害（用对象而非id，避免怪物死亡后id复用导致漏穿）
        self.sp_splash = sp_splash  # 白夜SP白银冰破弹：命中第一个敌人后对其3×3范围内敌人额外溅射(0.5=50%)冰伤
        self.element = "ice" if ice else element   # 弹丸元素类型（决定抗性结算与数字配色）
        self.attrs = attrs if attrs is not None else {}   # 攻击方属性快照（完整公式各乘区）

    def update(self):
        self.x += self.speed

    def draw(self, screen):
        if self.ult:
            if self.epic:
                # SP凯恩大招弹（华丽版）：超大型金红能量弹 + 三颗旋转光弧星 + 三段长拖尾
                t = pygame.time.get_ticks()
                ang = t / 90
                pygame.draw.circle(screen, (255, 130, 50), (self.x, self.y), 14)
                pygame.draw.circle(screen, (255, 215, 90), (self.x, self.y), 9)
                pygame.draw.circle(screen, (255, 248, 205), (self.x, self.y), 5)
                for i in range(3):                        # 旋转光弧小星
                    a = ang + i * 2.09
                    sx = self.x + 18 * math.cos(a)
                    sy = self.y + 18 * math.sin(a)
                    pygame.draw.circle(screen, (255, 200, 80), (int(sx), int(sy)), 3)
                for (dx, dy, r) in [(10, -4, 6), (20, 4, 4), (32, -3, 2)]:   # 三段长拖尾
                    pygame.draw.circle(screen, (255, 180, 70), (self.x - dx, self.y + dy), r)
            else:
                # 普通大招弹丸：大型金色能量弹 + 双段拖尾，明显区别于普通子弹
                pygame.draw.circle(screen, (255, 205, 60), (self.x, self.y), 9)
                pygame.draw.circle(screen, (255, 243, 170), (self.x, self.y), 5)
                pygame.draw.circle(screen, (255, 225, 110), (self.x - 8, self.y), 4)
                pygame.draw.circle(screen, (255, 225, 110), (self.x - 15, self.y), 2)
        elif self.ice:
            if self.sp_splash:
                # 白夜SP白银冰破弹：更大冰弹（蓝白核心 + 三颗旋转冰晶星 + 浅蓝拖尾）
                t = pygame.time.get_ticks()
                ang = t / 120
                pygame.draw.circle(screen, (120, 200, 255), (self.x, self.y), 9)
                pygame.draw.circle(screen, (225, 245, 255), (self.x, self.y), 4)
                for i in range(3):
                    a = ang + i * 2.09
                    sx = self.x + 11 * math.cos(a)
                    sy = self.y + 11 * math.sin(a)
                    pygame.draw.circle(screen, (190, 235, 255), (int(sx), int(sy)), 2)
                pygame.draw.circle(screen, (150, 215, 255), (self.x - 10, self.y), 3)
                pygame.draw.circle(screen, (170, 225, 255), (self.x - 17, self.y), 2)
            else:
                # 冰弹：浅蓝弹体 + 高光
                pygame.draw.circle(screen, (150, 210, 255), (self.x, self.y), 5)
                pygame.draw.circle(screen, (225, 245, 255), (self.x, self.y), 2)
        elif self.pierce:
            # 贯穿弹（琮）：细长高速弹体 + 拖尾，每穿一个怪物改变一次形态，
            # 穿满3个后形态耗尽消失。pierce_left 从3递减：3=未穿(蓝白)、2=穿1个(金色)、1=穿2个(红紫)。
            if self.pierce_left >= 3:       # 未穿透任何目标：蓝白初始弹
                ln, c2, c3 = (235, 245, 255), (215, 235, 255), (250, 252, 255)
            elif self.pierce_left == 2:     # 已穿1个：金色强化弹
                ln, c2, c3 = (255, 230, 150), (255, 205, 90), (255, 248, 205)
            else:                           # 已穿2个：红紫极限弹（穿满3个后消失）
                ln, c2, c3 = (255, 170, 150), (235, 120, 170), (255, 230, 220)
            pygame.draw.line(screen, ln, (self.x - 16, self.y), (self.x + 8, self.y), 4)
            pygame.draw.circle(screen, c2, (self.x, self.y), 6)
            pygame.draw.circle(screen, c3, (self.x, self.y), 3)
        else:
            pygame.draw.circle(screen, (190, 190, 190), (self.x, self.y), 4)


class FloatingText:
    """飘动的伤害数值：怪物每次受到伤害时显示，向上飘起并淡出。
       文本 Surface 在创建时渲染一次并缓存，飘动期间不再重复 render（大幅降低伤害数字多时的开销）。"""
    def __init__(self, x, y, text, color=(255, 90, 80), size=16):
        self.x, self.y = x, y
        self.text = text
        self.color = color
        self.size = size
        self.life = FPS          # 约1秒后消失
        self.vy = -0.9           # 上飘速度
        self._img = make_font(size).render(str(text), True, color)

    def update(self):
        self.y += self.vy
        self.life -= 1
        return self.life > 0

    def draw(self, screen):
        img = self._img
        screen.blit(img, (self.x - img.get_width() // 2, self.y))


class ParticleFx:
    """简单粒子特效：随机小颗粒向四周飘散（怪物死亡冰渣/灰烬等）。"""
    def __init__(self, x, y, color, n=10):
        self.x, self.y = x, y
        self.color = color
        self.life = 26
        self.parts = [(random.uniform(-3, 3), random.uniform(-4.5, -0.5),
                       random.randint(2, 5), random.uniform(-0.05, 0.05)) for _ in range(n)]

    def update(self):
        self.life -= 1
        return self.life > 0

    def draw(self, screen):
        t = 26 - self.life
        for (vx, vy, s, drift) in self.parts:
            px = self.x + vx * t
            py = self.y + vy * t + t * t * 0.08
            pygame.draw.rect(screen, self.color,
                             (int(px), int(py), s, s))


class FlashFx:
    """全屏闪光轰炸特效（雷纳·终末爆轰）：
       白色强光铺满全屏渐隐 + 中央扩散冲击环 + 漫天爆裂火花，模拟一次大爆炸。"""
    def __init__(self, cx, cy, life=24, max_alpha=210):
        self.cx, self.cy = cx, cy
        self.life = life
        self.max_alpha = max_alpha
        self.age = 0
        # 漫天爆裂火花（从中心向四周高速迸射的橙红碎屑）
        self.sparks = [(random.uniform(-9, 9), random.uniform(-9, 9),
                        random.randint(2, 5), random.uniform(-0.05, 0.05))
                       for _ in range(46)]

    def update(self):
        self.age += 1
        return self.age < self.life

    def draw(self, screen):
        t = self.age / max(1, self.life)
        w, h = screen.get_size()
        # 全屏白色闪光：前段强烈、后段渐隐
        alpha = int(self.max_alpha * (1 - t))
        if alpha > 0:
            flash = pygame.Surface((w, h), pygame.SRCALPHA)
            flash.fill((255, 250, 232, alpha))
            screen.blit(flash, (0, 0))
        # 中央扩散冲击环（爆炸冲击波）
        r = int(40 + t * t * max(w, h) * 1.3)
        lw = max(1, int(18 * (1 - t)))
        if lw > 0:
            pygame.draw.circle(screen, (255, 200, 120), (self.cx, self.cy), r, lw)
            pygame.draw.circle(screen, (255, 240, 200), (self.cx, self.cy), max(2, int(r * 0.7)), max(1, int(lw * 0.6)))
        # 漫天爆裂火花（橙红碎屑向四周迸射渐隐）
        for (vx, vy, s, drift) in self.sparks:
            px = self.cx + vx * t * (w * 0.45)
            py = self.cy + vy * t * (h * 0.45)
            c = (255, int(170 * (1 - t)), int(70 * (1 - t)))
            pygame.draw.rect(screen, c, (int(px), int(py), s, s))


class TargetMarkFx:
    """瓦伦丁锁定十字光标：狙击镜刻度环 + 十字准星刻度 + 中心红点。
       刻度点绕环旋转；epic=True（大招强化）为金色版 + 外圈扫描环 + 顶部瞄准光柱。"""
    def __init__(self, x, y, epic=False):
        self.x, self.y = x, y
        self.life = 36
        self.epic = epic

    def update(self):
        self.life -= 1
        return self.life > 0

    def draw(self, screen):
        t = 36 - self.life
        x, y = int(self.x), int(self.y)
        col = (255, 215, 90) if self.epic else (255, 105, 80)
        sub = (255, 245, 190) if self.epic else (255, 190, 170)
        r = 17
        # 旋转刻度点（绕环一圈，奇数点大偶数点小）
        for i in range(8):
            a = t * 0.025 + i * 0.785
            ox = x + int(r * math.cos(a)); oy = y + int(r * math.sin(a))
            pygame.draw.circle(screen, col, (ox, oy), 2 if i % 2 == 0 else 1)
        # 主圆环 + 外圈细环
        pygame.draw.circle(screen, col, (x, y), r, 2)
        pygame.draw.circle(screen, sub, (x, y), r + 3, 1)
        # 十字准星刻度（四方向伸出）
        for a in (0, 90, 180, 270):
            rad = math.radians(a)
            pygame.draw.line(screen, col,
                             (int(x + (r - 5) * math.cos(rad)), int(y + (r - 5) * math.sin(rad))),
                             (int(x + (r + 7) * math.cos(rad)), int(y + (r + 7) * math.sin(rad))), 2)
        # 中心红点（锁定核心）
        pygame.draw.circle(screen, (255, 55, 45), (x, y), 2)
        pygame.draw.circle(screen, (255, 160, 150), (x, y), 4, 1)
        if self.epic:
            # 外圈扫描环（呼吸扩散）
            s = (t % 16) / 16
            pygame.draw.circle(screen, (255, 230, 140), (x, y), int(r + 4 + 7 * s), 1)
            # 顶部瞄准光柱（金色）
            pygame.draw.line(screen, (255, 235, 150), (x, y - r - 8), (x, y - r - 24), 2)
            pygame.draw.circle(screen, (255, 245, 190), (x, y - r - 24), 2)


class SnipeLineFx:
    """瓦伦丁狙击线：枪口到目标的双层光轨（粗暗外线 + 亮色内线 + 端点光点）。
       epic=True（大招强化）为金色光轨，比普攻更亮更粗。"""
    def __init__(self, x1, y1, x2, y2, epic=False):
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2
        self.life = 10
        self.epic = epic

    def update(self):
        self.life -= 1
        return self.life > 0

    def draw(self, screen):
        a = self.life / 10
        col = (255, 215, 90) if self.epic else (150, 170, 190)
        x1, y1, x2, y2 = int(self.x1), int(self.y1), int(self.x2), int(self.y2)
        # 粗暗外线（光轨底色）
        pygame.draw.line(screen, (52, 58, 66), (x1, y1), (x2, y2), 4)
        # 亮色内线
        pygame.draw.line(screen, col, (x1, y1), (x2, y2), 2)
        # 端点光点（枪口 + 命中点）
        pygame.draw.circle(screen, col, (x1, y1), 2)
        pygame.draw.circle(screen, (255, 250, 230), (x2, y2), 3)
        # 命中点扩散光环
        pygame.draw.circle(screen, col, (x2, y2), 5 + int(4 * a), 1)


class ImpactFx:
    """瓦伦丁命中爆点：目标位置八向星芒扩散 + 中心亮点（约0.25秒）。
       epic=True（大招强化）为金色爆点，比普攻更华丽。"""
    def __init__(self, x, y, epic=False):
        self.x, self.y = x, y
        self.life = 15
        self.epic = epic

    def update(self):
        self.life -= 1
        return self.life > 0

    def draw(self, screen):
        t = 15 - self.life
        a = self.life / 15
        col = (255, 215, 90) if self.epic else (232, 236, 245)
        x, y = int(self.x), int(self.y)
        r = 4 + t * 1.6
        # 八向星芒
        for i in range(8):
            rad = i * 0.785
            pygame.draw.line(screen, col,
                             (int(x + r * 0.45 * math.cos(rad)), int(y + r * 0.45 * math.sin(rad))),
                             (int(x + r * math.cos(rad)), int(y + r * math.sin(rad))), 2)
        # 中心亮点 + 扩散环
        pygame.draw.circle(screen, (255, 252, 240), (x, y), 2 + int(2 * a))
        pygame.draw.circle(screen, col, (x, y), int(r * 0.6), 1)


class DeployFx:
    """瓦伦丁大招「战术再部署」：金色狙击镜刻度环扩散 + 12个旋转刻度 + 8条放射瞄准线 + 双环（约0.7秒）。"""
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.life = 42

    def update(self):
        self.life -= 1
        return self.life > 0

    def draw(self, screen):
        t = 42 - self.life
        x, y = int(self.x), int(self.y)
        r = 12 + t * 1.8
        col = (255, 215, 90) if self.life > 14 else (255, 170, 60)
        # 主环 + 内环
        pygame.draw.circle(screen, col, (x, y), int(r), 2)
        pygame.draw.circle(screen, (255, 245, 190), (x, y), int(r * 0.5), 1)
        # 12个旋转刻度点
        for i in range(12):
            a = t * 0.04 + i * 0.524
            ox = x + int(r * math.cos(a)); oy = y + int(r * math.sin(a))
            pygame.draw.circle(screen, col, (ox, oy), 2 if i % 3 else 1)
        # 8条放射瞄准线（从内环向外延伸）
        for i in range(8):
            a = i * 0.785 + t * 0.02
            pygame.draw.line(screen, col,
                             (int(x + r * 0.5 * math.cos(a)), int(y + r * 0.5 * math.sin(a))),
                             (int(x + (r + 10) * math.cos(a)), int(y + (r + 10) * math.sin(a))), 2)
        # 中心红点
        pygame.draw.circle(screen, (255, 80, 60), (x, y), 2)


class IceStormFx:
    """极乐冰宴特效：冰雨覆盖大招区域（蓝色半透明 + 下落的冰晶线条），约0.7秒后淡出消失。"""
    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.timer = 45                                  # 特效持续帧数
        self.rnd = random.Random(7)                      # 固定随机种子：冰晶位置稳定不闪烁
        self.drops = [(self.rnd.uniform(0, w), self.rnd.uniform(0, h)) for _ in range(26)]

    def update(self):
        self.timer -= 1
        return self.timer > 0

    def draw(self, screen):
        t = max(self.timer, 0)
        alpha = int(50 + (t / 45) * 90)                  # 越到后期越淡
        ov = pygame.Surface((int(self.w), int(self.h)), pygame.SRCALPHA)
        ov.fill((140, 210, 255, alpha // 2))             # 半透明冰蓝底
        phase = (45 - t) * 3                             # 冰晶下落相位
        for (dx, dy) in self.drops:
            yy = (dy + phase * 0.9) % self.h
            pygame.draw.line(ov, (225, 245, 255, min(230, alpha + 90)), (dx, yy), (dx, yy + 12), 2)
        pygame.draw.rect(ov, (170, 225, 255, min(190, alpha + 60)), ov.get_rect(), 2, border_radius=6)
        screen.blit(ov, (int(self.x), int(self.y)))


class EnergyBurstFx:
    """金色能量爆发特效：扩散光环 + 粒子向外爆发。
       里昂大招用大号（max_r=130）；SP凯恩大招弹命中用中号（max_r=42）。"""
    def __init__(self, x, y, max_r=130):
        self.x, self.y = x, y
        self.max_r = max_r
        self.timer = 30                                   # 特效持续帧数
        self.rnd = random.Random(11)
        n = 18 if max_r > 80 else 10
        self.parts = [(self.rnd.uniform(-0.42, 0.42) * max_r,
                       self.rnd.uniform(-0.42, 0.42) * max_r) for _ in range(n)]

    def update(self):
        self.timer -= 1
        return self.timer > 0

    def draw(self, screen):
        t = max(self.timer, 0)
        prog = 1 - t / 30                                  # 0→1 逐渐扩散
        r = 6 + prog * self.max_r
        alpha = max(0, int(170 - prog * 140))
        ring = pygame.Surface((int(r * 2) + 2, int(r * 2) + 2), pygame.SRCALPHA)
        pygame.draw.circle(ring, (255, 215, 90, alpha), (r + 1, r + 1), r, 3)
        pygame.draw.circle(ring, (255, 235, 150, alpha // 2), (r + 1, r + 1), r - 5, 1)
        screen.blit(ring, (int(self.x - r), int(self.y - r)))
        for (px, py) in self.parts:                        # 金色粒子向外飞出
            ex = self.x + px * prog
            ey = self.y + py * prog
            pygame.draw.circle(screen, (255, 230, 120), (int(ex), int(ey)), max(1, 4 - int(prog * 3)))


class WaterWaveFx:
    """卡斯珀高压水流：从单位向右横扫的蓝色多层水波，约0.4秒淡出。"""
    def __init__(self, x, y, w):
        self.x, self.y, self.w = x, y, w
        self.life = 24

    def update(self):
        self.life -= 1
        return self.life > 0

    def draw(self, screen):
        t = max(self.life, 0)
        alpha = int(60 + (t / 24) * 120)
        surf = pygame.Surface((int(self.w), 26), pygame.SRCALPHA)
        for i in range(3):
            yy = 8 + i * 5
            h = 6 + i * 3
            pygame.draw.ellipse(surf, (90, 190, 255, alpha), (i * 6, yy, max(6, self.w - i * 14), h))
        screen.blit(surf, (int(self.x - CELL_W * 0.5), int(self.y - 13)))


class WhirlpoolFx:
    """暗潮漩涡：蓝色旋转水涡（多层圆环 + 顺时针旋转水珠），持续约3秒。"""
    def __init__(self, x, y, w):
        self.x, self.y, self.w = x, y, w
        self.life = 90

    def update(self):
        self.life -= 1
        return self.life > 0

    def draw(self, screen):
        t = max(self.life, 0)
        phase = (90 - t) * 6
        cx = self.x + self.w // 2
        for ring in range(3):
            r = 14 + ring * 16
            alpha = max(40, int(160 - ring * 35))
            surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (80, 180, 255, alpha), (r, r), r, 3)
            screen.blit(surf, (int(cx - r), int(self.y - r)))
        for i in range(6):
            ang = math.radians(phase + i * 60)
            px = cx + math.cos(ang) * 22
            py = self.y + math.sin(ang) * 10
            pygame.draw.circle(screen, (160, 220, 255), (int(px), int(py)), 3)


class SoloBurstFx:
    """暴走独奏（大招专属特效）：金色放射音浪 + 冲击环 + 升腾音符爆发，约0.8秒。
    常驻光环另在角色绘制中显示（声波光圈+漂浮音符），两者视觉区分开。"""
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.life = 48
        self.rnd = random.Random(7)
        self.rays = [(self.rnd.uniform(-math.pi, math.pi), self.rnd.uniform(0.3, 1.0)) for _ in range(8)]
        self.notes = [(self.rnd.uniform(-0.5, 0.5), self.rnd.uniform(-1.0, -0.3)) for _ in range(8)]

    def update(self):
        self.life -= 1
        return self.life > 0

    def draw(self, screen):
        t = max(self.life, 0)
        prog = 1 - t / 48
        # 金色放射音浪
        for (a, sp) in self.rays:
            px = self.x + math.cos(a) * prog * 90 * sp
            py = self.y + math.sin(a) * prog * 90 * sp
            pygame.draw.line(screen, (255, 200, 90), (int(self.x), int(self.y)), (int(px), int(py)), 3)
        # 冲击环
        r = int(prog * 55)
        ring = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(ring, (255, 210, 120, max(0, int(160 - prog * 140))), (r + 1, r + 1), r, 3)
        screen.blit(ring, (int(self.x - r), int(self.y - r)))
        # 升腾音符
        for (nx, ny) in self.notes:
            px = self.x + nx * prog * 70
            py = self.y + ny * prog * 60
            pygame.draw.rect(screen, (255, 225, 150), (int(px - 3), int(py - 3), 6, 5))
            pygame.draw.circle(screen, (255, 225, 150), (int(px + 3), int(py - 5)), 3)


class SprayFx:
    """茯苓大招特效：绿色药雾喷向前方3格区域，飘散约0.7秒。"""
    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.timer = 40
        self.rnd = random.Random(21)
        self.drops = [(self.rnd.uniform(0, w), self.rnd.uniform(0, h)) for _ in range(22)]

    def update(self):
        self.timer -= 1
        return self.timer > 0

    def draw(self, screen):
        t = max(self.timer, 0)
        alpha = int(50 + (t / 40) * 80)
        ov = pygame.Surface((int(self.w), int(self.h)), pygame.SRCALPHA)
        ov.fill((150, 235, 170, alpha // 2))               # 半透明药雾底色
        phase = (40 - t) * 2
        for (dx, dy) in self.drops:
            yy = (dy + phase * 0.7) % self.h
            pygame.draw.circle(ov, (200, 250, 210, min(220, alpha + 70)), (dx, yy), 5)
        pygame.draw.rect(ov, (170, 240, 185, min(170, alpha + 50)), ov.get_rect(), 2, border_radius=6)
        screen.blit(ov, (int(self.x), int(self.y)))


class Defender:
    """防御单位（耕地者）。由 UNITS 数据驱动，behavior 决定行为。"""
    def __init__(self, uid, x, y):
        d = next(u for u in UNITS if u["uid"] == uid)
        self.uid = uid
        self.name = d["name"]
        self.is_sp = d["is_sp"]
        self.cost = d["cost"]
        self.behavior = d["behavior"]
        self.color = d["color"]
        self.x, self.y = x, y
        self.maxhp = d["hp"] if d["hp"] > 0 else 1   # 火元素数据 hp=0，内部用1占位（无生命值不显示血条）
        self.hp = self.maxhp
        self.produce = d.get("produce", 0)
        self.produce_iv = d.get("produce_iv", 0)
        self.attack = d.get("attack", 0)
        self.atk_iv = d.get("atk_iv", 0)
        self.ult = d.get("ult", 0)
        self.ult_cd = 0               # 大招冷却（帧）：初始0=就绪，释放后按数据秒数进入冷却
        self.ult_name = d.get("ult_name", "")
        # 行动系统 / 计时
        self.action = 0.0          # 行动累积值（见行动顺序系统）
        self.speed = 100.0         # 基础行动速度
        self.produce_timer = self.produce_iv * FPS if self.produce_iv else 0
        self.atk_timer = self.atk_iv * FPS if self.atk_iv else 0
        # ---- 一次性单位（沫/雷纳）：存活计时、引爆延迟后自动撤离 ----
        self.life_timer = int(d.get("life_time", 0) * FPS)   # 一次性存活时长（帧，0=非一次性）
        self.life_max = self.life_timer
        self.energy_total = d.get("energy_total", 0)          # 沫：4秒内总计产出能量
        self.boom_dmg = d.get("boom_dmg", 0)                  # 雷纳：引爆全场爆炸伤害
        self.boom_triggered = False                            # 雷纳是否已引爆（防重复）
        if d.get("behavior") == "melee":
            self.atk_timer = 0   # 诺瓦：初始冷却为0，范围内有敌人立即启动切割（反应快）
        self.ult_remain = 0        # 大招剩余连发数（凯恩用）
        self.core_light = 0        # 呼吸光效相位
        self.dmg_reduce = d.get("dmg_reduce", 0)   # 常驻减伤比例（布洛克固守姿态50%）
        # ---- 伤害结算属性（完整公式各乘区，默认值=基础，辅助角色可给加成）----
        self.atk_pct = d.get("atk_pct", 0.0)          # 攻加%（攻击×[1+攻加%]）
        self.flat_atk = d.get("flat_atk", 0.0)        # 固定攻（+固定攻击力）
        self.mult = d.get("mult", 1.0)                # 倍率（普攻=1.0，技能多段用）
        self.pierce_val = d.get("pierce", 0.0)        # 穿透（直接抵扣受击方有效防御）
        self.dmg_inc = d.get("dmg_inc", 0.0)          # 增伤%（攻击方）
        self.armor_reduce = d.get("armor_reduce", 0.0)  # 减防%（攻击方施加）
        self.resist_reduce = d.get("resist_reduce", 0.0)  # 减抗%（攻击方施加）
        self.crit_rate = d.get("crit_rate", 0.2)      # 暴击率（基础20%）
        self.crit_dmg = d.get("crit_dmg", 0.5)        # 暴击伤害加成（基础50%）
        # ---- 增益状态（辅助角色：埃利奥特光环/大招）----
        self.buff_atk = 0.0           # 常驻光环攻加%（离开光环范围后5秒消失）
        self.buff_atk_timer = 0       # 光环攻加剩余帧
        self._in_ell_rings = 0        # 本帧被几个埃利奥特振奋和弦光环覆盖（支持叠加）
        self.buff_atk_ult = 0.0       # 大招额外攻加%（8秒）
        self.buff_atk_ult_timer = 0   # 大招攻加剩余帧
        self.true_dmg_left = 0        # 剩余附带真实伤害次数（暴走独奏）
        self.true_dmg_val = 0         # 附带真实伤害值/次
        # ---- 赫利俄（聚能棱镜/恒光刻印增益）----
        self.buff_crit_rate = 0.0     # 聚能棱镜：暴击率加成（正前方一格友方，赫利俄离场直接消失）
        self.buff_crit_dmg = 0.0      # 聚能棱镜：暴击伤害加成
        self.buff_helio_x = None      # 聚能棱镜来源赫利俄的 x 坐标（用于校验离场后清除增益）
        self.eternal_seal = False     # 恒光刻印标记（永久攻速+100%、抗性穿透+50%，不随赫利俄离场消失）
        self.prism_bleed_timer = 5 * FPS   # 聚能棱镜负面代价：被赋能单位每5秒扣10点血（首扣等待5秒）
        self.buff_dmg_inc = 0.0            # 增伤buff（茯苓SP愈光投瓶30%全属性增伤）
        self.buff_dmg_inc_timer = 0        # 增伤buff剩余帧数（到期归零）
        self.anim_t = 0               # 动画帧计数（常驻光环脉动/音符漂浮等绘制用）
        # ---- 瓦伦丁（狙击型）----
        self.sniper_ult = 0           # 战术再部署强化剩余帧数（大招期间每2次攻击额外狙杀）
        self.sniper_shots = 0         # 狙击次数计数（每2次攻击触发额外狙杀）
        self.shield = 0            # 护盾值（布洛克大招获得1000）
        self.taunt_timer = 0       # 嘲讽剩余帧数（布洛克大招4秒）
        self.invuln_timer = 0      # 无敌帧（白夜SP永夜：释放大招期间自身无敌，怪物攻击完全免疫）
        self.untargetable = True if d.get("behavior") == "fire" else False  # 火元素无生命值，怪物不攻击它
        # ---- 诺瓦（近战切割）----
        self.melee_range = d.get("range", 3)     # 攻击范围：自身格及前方N格
        self.swing_sec = d.get("swing_sec", 4)   # 电锯持续切割秒数
        self.swing_timer = 0                     # 切割剩余帧数
        self.ult_tick = 0                        # 锯刃风暴每段伤害间隔累积
        # ---- 罗格（2×3横扫格斗者 / SP三元素形态）----
        self.rog_range = d.get("range", 2)       # 2×3矩形：自身前方N格（横向2格）
        self.rog_rows = d.get("rows", 3)         # 纵向行数：当前行±1行（3行）
        self.rog_form = 0                        # SP形态索引：0火/1冰/2毒（基础罗格忽略）
        self.rog_hit_this = False                # 本次普攻是否命中（触发三行裂斩判定用）
        # ---- 莱昂纳多（链式电弧）----
        self.chain_targets = d.get("chain_targets", 3)   # 每次攻击电弧目标数
        self.splash = d.get("splash", 0.5)               # 溅射比例（同格其它敌人）
        # ---- 伊格尼斯（燃烧瓶）----
        self.fuse_timer = d.get("fuse", 30)      # 引信延迟帧（0.5秒后投掷）
        self.fire_dmg = d.get("fire_dmg", 800)   # 爆炸瞬间伤害
        self.fire_dot = d.get("fire_dot", 150)   # 火区持续伤害/秒
        self.fire_sec = d.get("fire_sec", 4)     # 火区持续秒数
        self.burn = d.get("burn", 100)           # 灼烧伤害/秒
        self.burn_sec = d.get("burn_sec", 4)     # 灼烧持续秒数
        # ---- 茯苓（治疗支援）----
        self.heal = d.get("heal", 0)             # 包扎每秒治疗量
        self.heal_iv = d.get("heal_iv", 0)       # 治疗间隔（秒）
        self.heal_timer = 0                      # 治疗计时
        self.ult_hot = d.get("ult_hot", 50)      # 大招后续回复量/秒
        self.ult_hot_sec = d.get("ult_hot_sec", 4)  # 大招后续回复持续秒数
        self.hot_hp = 0                          # 当前持续回复量/秒（大招挂上）
        self.hot_timer = 0                       # 持续回复剩余帧数
        self.heal_buff = d.get("heal_buff", 0.0)     # 茯苓SP投瓶附带的增伤比例（0.30=30%全属性增伤）
        self.heal_buff_sec = d.get("heal_buff_sec", 0)  # 投瓶增伤buff持续秒数

    # ---- 大招：统一入口 ----
    def cast_ult(self, ctx):
        # 烬（普通+SP）没有大招：SP用空格切换形态（不进本方法），直接返回 False，避免误扣大招次数
        if self.behavior == "rog":
            return False
        # 测试模式/沙盒模式/DPS试炼场：大招无冷却（沙盒通过 scene.sandbox 标记，不影响全局测试开关）
        test_mode = (getattr(ctx["scene"], "sandbox", False)
                     or getattr(ctx["scene"].game, "cheat", False)
                     or getattr(ctx["scene"], "dps_mode", False))
        if self.ult_remain <= 0 and self.ult_cd > 0 and not test_mode:
            return False
        if self.ult_cd <= 0 or test_mode:
            if self.behavior == "energy":
                ctx["scene"].energy += self.ult         # 里昂：立即产能源
                # 释放金色能量爆发特效（扩散光环 + 粒子），让大招明显可感知
                ctx["scene"].burst_fx.append(EnergyBurstFx(self.x, self.y))
                self.ult_cd = next(u for u in UNITS if u["uid"] == self.uid)["ult_cd"] * FPS
            elif self.behavior == "shooter":
                # 普通凯恩连发 ult 次；SP凯恩逐帧发射5枚（每帧1枚，扇形散布）
                self.ult_remain = 5 if self.is_sp else (self.ult if self.ult else 0)
                self.ult_cd = next(u for u in UNITS if u["uid"] == self.uid)["ult_cd"] * FPS
            elif self.behavior == "blocker":
                # 布洛克：铁壁嘲讽——吸引自身行及相邻行敌人强制攻击自己4秒，并获得1000护盾
                self.taunt_timer = 4 * FPS
                self.shield = 1000
                self.ult_cd = next(u for u in UNITS if u["uid"] == self.uid)["ult_cd"] * FPS
            elif self.behavior == "melee":
                # 诺瓦：锯刃风暴——向前方突进4格，路径上敌人受5段×200切割伤害
                self.ult_remain = 5
                self.ult_tick = 0
                self.ult_cd = next(u for u in UNITS if u["uid"] == self.uid)["ult_cd"] * FPS
            elif self.behavior == "pierce":
                # 琮：勘测连射——连续发射2发贯穿弹，每发100，穿透整行所有敌人
                self.ult_remain = 2
                self.ult_cd = next(u for u in UNITS if u["uid"] == self.uid)["ult_cd"] * FPS
            elif self.behavior == "ice":
                if self.is_sp:
                    # 白夜SP·永夜：自身行及相邻两行前方展开冰场4秒（冻结+每秒600冰伤），释放期间自身无敌
                    ctx["firezones"].append(IceNightFx(self.x, self.y, self))
                    self.invuln_timer = 4 * FPS          # 大招期间自身无敌
                    ctx["scene"].fx.append(FloatingText(self.x, self.y - 34, "永夜冰场！", DAMAGE_COLOR_ICE, 20))
                else:
                    # 白夜：极乐冰宴——自身行及相邻行（上下各1行）前方5格：
                    # 500冰伤 + 冻结3秒（无法移动/攻击）+ 冻伤100/秒×3秒
                    for m in ctx["monsters"][:]:
                        if ((m.giant or abs(m.y - self.y) < CELL_H * 1.5) and
                                self.x - CELL_W * 0.5 <= m.x <= self.x + 5.5 * CELL_W):
                            self.hit_monster(ctx, m, self.ult, "ice")
                            m.freeze_timer = 3 * FPS
                            m.cold_timer = max(m.cold_timer, 5 * FPS)   # 冻结同时获得寒冷状态
                            m.frost_dmg = 100
                            m.frost_timer = 3 * FPS
                            snap = self.atk_snapshot(); snap["crit_rate"] = 0.0
                            m.frost_attrs = snap
                            if m.hp <= 0:
                                m.die(ctx["scene"])
                    # 释放冰雨特效：覆盖大招范围（自身行±1行 × 前方5格）
                    ctx["scene"].ice_fx.append(
                        IceStormFx(self.x - CELL_W * 0.5, self.y - CELL_H * 1.5,
                                   5.5 * CELL_W, 3 * CELL_H))
                self.ult_cd = next(u for u in UNITS if u["uid"] == self.uid)["ult_cd"] * FPS
            elif self.behavior == "healer":
                # 茯苓：急救喷雾——前方3格范围友方：瞬间回300 + 每秒50持续4秒（总500），绿色药雾特效
                for d in ctx["defenders"]:
                    if (d.hp > 0 and abs(d.y - self.y) < 45 and
                            self.x - CELL_W * 0.5 <= d.x <= self.x + 3.5 * CELL_W):
                        d.hp = min(d.maxhp, d.hp + 300)
                        d.hot_hp = self.ult_hot
                        d.hot_timer = self.ult_hot_sec * FPS
                        ctx["scene"].fx.append(FloatingText(d.x, d.y - 30, "+300", (120, 220, 120), 18))
                # 释放绿色药雾特效：覆盖自身行前方3格
                ctx["scene"].spray_fx.append(
                    SprayFx(self.x - CELL_W * 0.5, self.y - CELL_H * 0.8, 4 * CELL_W, CELL_H * 1.6))
                self.ult_cd = next(u for u in UNITS if u["uid"] == self.uid)["ult_cd"] * FPS
            elif self.behavior == "healer_sp":
                # 茯苓SP：全域圣愈——全屏所有友方瞬间回复280，并清除所有负面debuff，全屏绿色圣愈光环
                for d in ctx["defenders"]:
                    if d.hp <= 0:
                        continue
                    d.hp = min(d.maxhp, d.hp + self.ult)
                    # 清除负面debuff：冻结/灼烧/寒冷/潮湿/麻痹/腐蚀等
                    for attr in ("burn_timer", "frost_timer", "freeze_timer",
                                 "cold_timer", "wet_timer", "paralyze_timer", "poison_timer"):
                        if getattr(d, attr, 0) > 0:
                            setattr(d, attr, 0)
                    ctx["scene"].fx.append(
                        FloatingText(d.x, d.y - 30, f"+{self.ult}", (150, 240, 170), 16))
                # 全屏圣愈药雾特效（覆盖整个战场网格区）
                ctx["scene"].spray_fx.append(
                    SprayFx(0, GRID_TOP, SCREEN_WIDTH, GRID_BOTTOM - GRID_TOP))
                self.ult_cd = next(u for u in UNITS if u["uid"] == self.uid)["ult_cd"] * FPS
            elif self.behavior == "chain":
                # 莱昂纳多：雷暴领域——导棍插地，3行×前方5格内所有敌人600雷伤
                for m in ctx["monsters"][:]:
                    if ((m.giant or abs(m.y - self.y) < CELL_H * 1.5) and
                            self.x - CELL_W * 0.5 <= m.x <= self.x + 5.5 * CELL_W):
                        self.hit_monster(ctx, m, self.ult, "bolt")
                        if m.hp <= 0:
                            m.die(ctx["scene"])
                # 释放雷暴领域特效：覆盖大招范围（3行 × 前方5格）
                ctx["scene"].storm_fx.append(
                    StormFx(self.x - CELL_W * 0.5, self.y - CELL_H * 1.5, 5.5 * CELL_W, 3 * CELL_H))
                self.ult_cd = next(u for u in UNITS if u["uid"] == self.uid)["ult_cd"] * FPS
            elif self.behavior == "water":
                if self.is_sp:
                    # 卡斯珀SP·归墟大潮：整行1000水伤，并一次性把整行敌人击退至该行最末端格子
                    row_right = GRID_LEFT + (GRID_COLS - 1) * CELL_W + CELL_W // 2
                    for m in ctx["monsters"][:]:
                        if m.giant or abs(m.y - self.y) < 45:
                            self.hit_monster(ctx, m, self.ult, "water")
                            m.x = row_right          # 一次性强击退：推到该行最末端格子
                            m.kb_x = None
                            if m.hp <= 0:
                                m.die(ctx["scene"])
                    # 整行大水潮特效 + 文字提示
                    ctx["scene"].water_fx.append(
                        WaterWaveFx(GRID_LEFT, self.y, GRID_COLS * CELL_W + CELL_W))
                    ctx["scene"].fx.append(FloatingText(self.x, self.y - 34, "归墟大潮！", DAMAGE_COLOR_WATER, 20))
                else:
                    # 普通卡斯珀：暗潮漩涡——前方4格持续3秒，每段200水伤+击退4格
                    self.ult_remain = 3
                    self.ult_tick = 0
                self.ult_cd = next(u for u in UNITS if u["uid"] == self.uid)["ult_cd"] * FPS
            elif self.behavior == "sniper":
                # 瓦伦丁：战术再部署——强化15秒，期间每2次攻击立即额外再狙杀一次
                self.sniper_ult = 15 * FPS
                self.sniper_shots = 0
                ctx["scene"].snipe_fx.append(DeployFx(self.x, self.y))   # 金色准星圆环扩散特效
                self.ult_cd = next(u for u in UNITS if u["uid"] == self.uid)["ult_cd"] * FPS
            elif self.behavior == "buffer":
                # 埃利奥特：暴走独奏——3×3友方攻击力额外+50%（8秒），
                # 且范围内每位友方后续10次攻击附带20点对应元素真实伤害
                for d in ctx["defenders"]:
                    if d.hp > 0 and abs(d.x - self.x) < CELL_W * 1.5 and abs(d.y - self.y) < CELL_H * 1.5:
                        d.buff_atk_ult = 0.5
                        d.buff_atk_ult_timer = 8 * FPS
                        d.true_dmg_left = 10
                        d.true_dmg_val = 20
                # 大招特效：金色放射音浪爆发（与常驻光环区分）
                ctx["scene"].sonic_fx.append(SoloBurstFx(self.x, self.y))
                self.ult_cd = next(u for u in UNITS if u["uid"] == self.uid)["ult_cd"] * FPS
            elif self.behavior == "helio":
                # 赫利俄：恒光刻印——给正前方一格友方永久刻印【恒光】：
                # 100%攻速提升（攻击间隔减半）+ 50%抗性穿透；不随自身离场消失，目标阵亡才消失
                target = None
                for d in ctx["defenders"]:
                    if d is self or d.hp <= 0:
                        continue
                    if abs(d.y - self.y) < CELL_H * 0.6 and self.x + CELL_W * 0.5 <= d.x <= self.x + CELL_W * 1.5:
                        target = d
                        break
                if target is not None:
                    if getattr(target, "eternal_seal", False):
                        ctx["scene"].fx.append(FloatingText(self.x, self.y - 34, "已刻印恒光", COLOR_GOLD, 16))
                    else:
                        target.eternal_seal = True
                        target.atk_iv = max(0.2, target.atk_iv / 2)   # 攻速+100%（间隔减半）
                        target.resist_reduce += 0.5                    # 抗性穿透+50%
                        ctx["scene"].fx.append(FloatingText(self.x, self.y - 34, "恒光刻印！", COLOR_GOLD, 18))
                        ctx["scene"].fx.append(FloatingText(target.x, target.y - 34, "恒光", COLOR_GOLD, 16))
                        # 释放金色光束刻印特效：从赫利俄棱镜射向前方友方
                        ctx["scene"].helio_seal_fx.append(HelioSealFx(self.x, self.y, target.x, target.y))
                else:
                    ctx["scene"].fx.append(FloatingText(self.x, self.y - 34, "前方无友方", (200, 200, 200), 14))
                self.ult_cd = next(u for u in UNITS if u["uid"] == self.uid)["ult_cd"] * FPS
            elif self.behavior == "fire":
                return False   # 伊格尼斯无大招（一次性单位）
            if test_mode:
                self.ult_cd = 0   # 测试模式：大招无冷却，可连续释放
            return True
        return False

    def take_damage(self, n):
        """承受伤害：无敌(白夜SP永夜) → 常驻减伤(固守姿态) → 护盾吸收 → 扣血，返回实际扣血量。"""
        # 雷纳引爆延迟期间完全无敌（确保终末爆轰必然触发）
        if self.behavior == "rena" and self.life_timer > 0:
            return 0
        if self.invuln_timer > 0:
            return 0          # 无敌：完全免疫本次伤害
        if self.dmg_reduce > 0:
            n = n * (1 - self.dmg_reduce)
        if self.shield > 0:
            absorbed = min(n, self.shield)
            self.shield -= absorbed
            n -= absorbed
        self.hp -= n
        return n

    def _pierce_spawn_x(self, ctx):
        """贯穿弹出生点修正：若怪物已贴脸（身体越过发射点左侧附近），
           弹丸直接放到该怪物的中心位置，保证出生即命中贴脸怪；
           否则从单位右前方正常发出。"""
        bx = self.x + 40
        best = None
        for m in ctx["monsters"]:
            mw = 66 if m.giant else 28
            # 贴脸判定：怪身体左缘在发射点左侧（出生点无法自然命中），
            # 且身体右缘仍在单位左缘60px范围内（怪已走到单位面前/身后）
            if (m.giant or abs(m.y - self.y) < 45) and m.x < bx and m.x + mw > self.x - 60:
                if best is None or m.x > best.x:
                    best = m
        if best is not None:
            return best.x + (33 if best.giant else 14)   # 贴脸怪中心（巨怪66宽/普通28宽）
        return bx

    def atk_snapshot(self):
        """攻击属性快照：发射弹丸/施放持续伤害时传给结算系统，
           防止攻击方属性变化（如辅助增益）导致中途伤害不一致。
           攻加% = 自身攻加% + 光环攻加% + 大招额外攻加%（若生效）；
           暴击率/爆伤 = 自身 + 赫利俄聚能棱镜加成（正前方一格友方）；
           附带真实伤害 = 暴走独奏剩余配额。"""
        atk_pct = self.atk_pct + self.buff_atk
        if self.buff_atk_ult_timer > 0:
            atk_pct += self.buff_atk_ult
        return dict(atk_pct=atk_pct, flat_atk=self.flat_atk, mult=self.mult,
                    pierce=self.pierce_val, dmg_inc=self.dmg_inc + self.buff_dmg_inc,
                    armor_reduce=self.armor_reduce, resist_reduce=self.resist_reduce,
                    crit_rate=self.crit_rate + self.buff_crit_rate,
                    crit_dmg=self.crit_dmg + self.buff_crit_dmg,
                    true_dmg=(self.true_dmg_val if self.true_dmg_left > 0 else 0))

    def consume_true_dmg(self):
        """消耗一次附带真实伤害次数（每次攻击动作发射/结算时调用）。"""
        if self.true_dmg_left > 0:
            self.true_dmg_left -= 1

    def set_rog_form(self, form):
        """罗格SP三元素形态切换：0火(炽焰征伐)/1冰(霜狱禁锢)/2毒(腐毒蚀骨)。
           普攻伤害随形态替换（火100/冰60/毒58），元素与附加状态在攻击逻辑中按形态区分。"""
        self.rog_form = form % 3
        self.attack = (100, 60, 58)[self.rog_form]

    def _snipe(self, ctx, m):
        """瓦伦丁定点狙杀：狙击镜刻度锁定光标 + 双层光轨狙击线 + 命中星芒爆点 + 瞬间命中结算。
           epic=True（大招强化期间）所有特效为金色史诗版，更华丽。"""
        epic = self.sniper_ult > 0
        ctx["scene"].cross_fx.append(TargetMarkFx(m.x, m.y - 20, epic=epic))
        ctx["scene"].snipe_fx.append(SnipeLineFx(self.x + 16, self.y - 14, m.x, m.y - 14, epic=epic))
        ctx["scene"].snipe_fx.append(ImpactFx(m.x, m.y - 8, epic=epic))
        self.hit_monster(ctx, m, self.attack, "physical")
        if m.hp <= 0:
            m.die(ctx["scene"])

    def hit_monster(self, ctx, m, base_atk, element="physical", mult=None, kind="aoe"):
        """对单个怪物结算一次伤害并显示飘字（普攻/大招/多段统一入口）。
        攻击属性取自身快照，受击属性取怪物防御/抗性；
        命中时触发元素状态附加与元素反应（感电/爆炸额外伤害在此结算）；
        返回(伤害值, 是否暴击)，怪物死亡由调用方负责移除。"""
        if getattr(m, "spawn_protect", False):
            # 生成保护：怪物刚生成在最后一格，尚未走到第二格，本发攻击不结算
            return (0, False)
        snap = self.atk_snapshot()
        td = snap.pop("true_dmg", 0)     # 真实伤害不参与公式结算，单独附加
        if mult is not None:
            snap["mult"] = mult
        # 元素状态附加与元素反应（攻击动作命中时触发；持续伤害不走此入口）
        pre_resist = m.resist_of(element)      # 命中前抗性快照（避免本发附加的寒冷影响本次伤害）
        bonus, extras = apply_elemental_hit(element, m, base_atk, ctx["monsters"])
        snap["dmg_inc"] = snap.get("dmg_inc", 0.0) + bonus
        dmg, crit = DamageSystem.calc(base_atk=base_atk, element=element,
                                      defense=m.defense, resist=pre_resist, **snap)
        # 附带真实伤害（埃利奥特暴走独奏）：无视防御/抗性/暴击直接附加，每次攻击动作消耗一次
        if td:
            dmg += td
            self.consume_true_dmg()
        m.take_hit(dmg, kind)
        ctx["scene"].fx.append(FloatingText(m.x, m.y - 26, f"-{dmg}",
                                            DamageSystem.text_color(element, False, crit),
                                            20 if crit else 16))
        # 感电/爆炸额外伤害（雷元素反应产物）
        for (t, ed, el, label) in extras:
            if t.hp > 0 and t in ctx["monsters"]:
                t.take_hit(ed, "explosive" if label == "爆炸" else "aoe")
                ctx["scene"].fx.append(FloatingText(t.x, t.y - 26, f"-{ed}",
                                                    DamageSystem.text_color(el), 14))
                if t.hp <= 0:
                    t.die(ctx["scene"])
        return dmg, crit

    # ---- 每帧更新（行为分派）----
    def update(self, ctx, mouse_pos):
        # ---- 一次性单位 ----
        # 沫：落地启动储能罐，持续4秒产出总计300能量（每秒产一个能源球自动拾取），结束自动撤离
        if self.behavior == "mo":
            self.life_timer -= 1
            self.produce_timer -= 1
            if self.produce_timer <= 0:
                sec = max(1, self.life_max // FPS)                      # 存活秒数（默认4）
                value = max(1, self.energy_total // sec)                # 每秒产出量
                ctx["orbs"].append(EnergyOrb(self.x + 6, self.y - 30, value, self.y + 8))
                self.produce_timer = FPS
            if self.life_timer <= 0:
                self.hp = 0        # 能量核心烧尽，供能结束自动撤离（被击杀归零也会在此路径被移除）
            return
        # 雷纳：部署0.8秒后引爆全场，对全体敌人造成无视防具防御的爆炸伤害，引爆后撤离
        if self.behavior == "rena":
            self.life_timer -= 1
            if self.life_timer <= 0 and not self.boom_triggered:
                self.boom_triggered = True
                for m in list(ctx["monsters"]):
                    if getattr(m, "spawn_protect", False):
                        continue
                    # 雷纳同样享受增幅（赫利俄暴击/爆伤、埃利奥特攻加、增伤等）：
                    # 结算时传入自身攻击快照，让所有增益作用于爆炸伤害
                    snap = self.atk_snapshot()
                    td = snap.pop("true_dmg", 0)      # 真实伤害不参与公式，单独附加
                    dmg, crit = DamageSystem.calc(base_atk=self.boom_dmg, element="physical",
                                                  defense=0, resist=m.resist_of("physical"), **snap)
                    if td:
                        dmg += td
                        self.consume_true_dmg()
                    m.take_hit(dmg, "explosive")     # 爆炸：无视一切防具/护甲防御直接扣血
                    ctx["scene"].fx.append(FloatingText(m.x, m.y - 30, f"-{dmg}",
                                                        DAMAGE_COLOR_BOOM, 17 if crit else 13))
                    ctx["scene"].fx.append(ParticleFx(m.x, m.y, (120, 95, 70), 10))   # 爆炸灼灰
                ctx["scene"].fx.append(ParticleFx(self.x, self.y, (240, 160, 70), 30))
                ctx["scene"].fx.append(FloatingText(self.x, self.y - 40, "终末爆轰！", (255, 200, 90), 20))
                getattr(ctx["scene"], "flash_fx", []).append(FlashFx(self.x, self.y))   # 全屏闪光轰炸
                self.hp = 0        # 爆破装备损毁，引爆后撤离
            return
        # 能源单位：产出能源球
        if self.behavior == "energy" and self.produce_iv:
            self.produce_timer -= 1
            if self.produce_timer <= 0:
                # 产出能源球：价值按难度调整，落地后鼠标移到球上拾取
                value = ctx["scene"].game.energy_value(self.produce)
                ctx["orbs"].append(EnergyOrb(self.x + 6, self.y - 30, value, self.y + 8))
                self.produce_timer = self.produce_iv * FPS
        # 远程单位：找同行前方怪物发射子弹（巨型怪横跨全部行可被任意行打）
        if self.behavior == "shooter" and self.attack:
            target = None
            for m in ctx["monsters"]:
                if not getattr(m, "spawn_protect", False) and \
                   (m.giant or abs(m.y - self.y) < 45) and m.x + (66 if m.giant else 0) > self.x:
                    target = m
                    break
            if self.ult_remain > 0:
                self.ult_remain -= 1
                if target:
                    snap = self.atk_snapshot()
                    self.consume_true_dmg()
                    if self.is_sp:
                        # SP凯恩大招：逐帧发射1枚（共5帧发完5枚），按剩余数做扇形垂直散布，
                        # 飞行时形成连珠+扇形效果，不会重叠成一颗
                        off = (self.ult_remain - 2) * 8
                        ctx["bullets"].append(Bullet(self.x + 40, self.y + off, self.ult, ult=True, epic=True,
                                                     attrs=snap))
                    else:
                        ctx["bullets"].append(Bullet(self.x + 40, self.y, self.attack, ult=True,
                                                     attrs=snap))
            else:
                self.atk_timer -= 1
                if self.atk_timer <= 0 and target:
                    snap = self.atk_snapshot()
                    self.consume_true_dmg()
                    ctx["bullets"].append(Bullet(self.x + 40, self.y, self.attack, attrs=snap))
                    if self.is_sp:   # SP凯恩双发
                        ctx["bullets"].append(Bullet(self.x + 40, self.y + 5, self.attack, attrs=snap))
                        if random.random() < 0.2:   # 20%额外连发5枚
                            for _ in range(5):
                                ctx["bullets"].append(Bullet(self.x + 40, self.y, self.attack, attrs=snap))
                    self.atk_timer = self.atk_iv * FPS
        # 贯穿单位（琮）：发射极快贯穿弹，穿透直线上的敌人
        if self.behavior == "pierce" and self.attack:
            target = None
            for m in ctx["monsters"]:
                # 目标范围放宽到贴脸怪（身体左缘在单位左侧60px内）：贴脸时也能被贯穿弹命中
                if (m.giant or abs(m.y - self.y) < 45) and m.x + (66 if m.giant else 0) > self.x - 60:
                    target = m
                    break
            if self.ult_remain > 0:
                self.ult_remain -= 1
                if target:
                    snap = self.atk_snapshot()
                    self.consume_true_dmg()
                    # 大招：勘测连射——连续发射2发贯穿弹，每发100，穿透整行所有敌人
                    ctx["bullets"].append(Bullet(self._pierce_spawn_x(ctx), self.y, self.ult, speed=60,
                                                 pierce=True, pierce_max=999, ult=True,
                                                 attrs=snap))
            else:
                self.atk_timer -= 1
                if self.atk_timer <= 0 and target:
                    snap = self.atk_snapshot()
                    self.consume_true_dmg()
                    # 普通贯穿弹：80伤害，速度适中（便于看清穿透3个目标的形态变化过程），穿透直线上的最多3名敌人
                    ctx["bullets"].append(Bullet(self._pierce_spawn_x(ctx), self.y, self.attack, speed=40,
                                                 pierce=True, pierce_max=3,
                                                 attrs=snap))
                    self.atk_timer = self.atk_iv * FPS
        # 冰霜单位（白夜）：发射冰弹（冰元素伤害 + 命中减速/寒冷）
        #   白夜=凝霜弹（普通冰弹）；白夜SP=白银冰破弹（更大冰弹，命中后3×3范围溅射50%冰伤）
        if self.behavior == "ice" and self.attack:
            target = None
            for m in ctx["monsters"]:
                if (m.giant or abs(m.y - self.y) < 45) and m.x + (66 if m.giant else 0) > self.x:
                    target = m
                    break
            self.atk_timer -= 1
            if self.atk_timer <= 0 and target:
                snap = self.atk_snapshot()
                self.consume_true_dmg()
                if self.is_sp:
                    # 白夜SP：白银冰破弹——发射时带 3×3 溅射标记（75%）
                    ctx["bullets"].append(Bullet(self.x + 40, self.y, self.attack, ice=True,
                                                 sp_splash=0.75, attrs=snap))
                else:
                    ctx["bullets"].append(Bullet(self.x + 40, self.y, self.attack, ice=True,
                                                 attrs=snap))
                self.atk_timer = self.atk_iv * FPS
        # 火元素单位（伊格尼斯）：引信倒计时 -> 投掷燃烧瓶（爆炸+火区）-> 跑路消失
        if self.behavior == "fire":
            if self.fuse_timer < 0:
                return   # 已投掷消失，不再执行（防御重复触发）
            self.fuse_timer -= 1
            if self.fuse_timer <= 0:
                ctx["firezones"].append(FireZone(self.x, self.y, self))
                # 爆炸瞬间：对火区范围内（自身格+前方1格）所有敌人造成800爆炸伤害
                for m in ctx["monsters"][:]:
                    if (m.giant or abs(m.y - self.y) < CELL_H * 0.7) and self.x - CELL_W * 0.5 <= m.x <= self.x + CELL_W * 1.5:
                        self.hit_monster(ctx, m, self.fire_dmg, "fire")
                        if m.hp <= 0:
                            m.die(ctx["scene"])
                self.fuse_timer = -1   # 锁定：只投掷一次
                self.hp = -1           # 跑路消失（由战斗场景统一移除）
        # 莱昂纳多（链式电弧）：每1.5秒释放三道电弧，对范围内(3行×前方4格)敌人雷伤；
        # 电弧可弹跳至附近敌人；被击中的目标同格其它敌人受50%溅射
        if self.behavior == "chain" and self.attack:
            self.atk_timer -= 1
            if self.atk_timer <= 0:
                self.atk_timer = self.atk_iv * FPS
                cands = [m for m in ctx["monsters"]
                         if (m.giant or abs(m.y - self.y) < CELL_H * 1.5)
                         and self.x - CELL_W * 0.5 <= m.x <= self.x + (self.melee_range + 0.5) * CELL_W]
                cands.sort(key=lambda m: (m.x, abs(m.y - self.y)))   # 最近的敌人优先
                for t in cands[: self.chain_targets]:
                    self.hit_monster(ctx, t, self.attack, "bolt")
                    ctx["scene"].bolt_fx.append(BoltFx(self.x, self.y - 14, t.x, t.y - 14))
                    # 同格溅射：除初始目标外，与目标同一格(及紧邻格)的敌人受50%伤害
                    for m in ctx["monsters"][:]:
                        if m is not t and abs(m.y - t.y) < CELL_H * 0.7 and abs(m.x - t.x) < CELL_W * 0.7:
                            self.hit_monster(ctx, m, self.attack, "bolt", mult=self.splash)
                            # 溅射电弧：闪电从初始目标弹跳连接到溅射目标（次级电弧特效）
                            ctx["scene"].bolt_fx.append(BoltFx(t.x, t.y - 14, m.x, m.y - 14))
                            if m.hp <= 0:
                                m.die(ctx["scene"])
                    if t.hp <= 0 and t in ctx["monsters"]:
                        ctx["monsters"].remove(t)
        # 近战单位（诺瓦）：电锯切割 + 锯刃风暴大招
        if self.behavior == "melee":
            if self.ult_remain > 0:
                # 大招：每0.5秒一段，对前方4格内所有敌人造成200切割伤害（共5段）
                self.ult_tick += 1
                if self.ult_tick >= FPS // 2:
                    self.ult_tick = 0
                    self.ult_remain -= 1
                    for m in ctx["monsters"][:]:
                        if (m.giant or abs(m.y - self.y) < 45) and self.x - CELL_W * 0.5 <= m.x <= self.x + 4.5 * CELL_W:
                            self.hit_monster(ctx, m, self.ult, "physical")
                            if m.hp <= 0:
                                m.die(ctx["scene"])
            elif self.swing_timer > 0:
                # 电锯持续切割：每秒一次，对自身格+前方3格内所有敌人造成伤害
                self.swing_timer -= 1
                if self.swing_timer % FPS == 0:
                    for m in ctx["monsters"][:]:
                        if (m.giant or abs(m.y - self.y) < 45) and self.x - CELL_W * 0.5 <= m.x <= self.x + (self.melee_range + 0.5) * CELL_W:
                            self.hit_monster(ctx, m, self.attack, "physical")
                            if m.hp <= 0:
                                m.die(ctx["scene"])
            else:
                # 切割周期：只要攻击范围内出现敌人就立即启动切割（反应快）。
                # 无敌人时冷却清零，敌人一进入范围立刻启动；切割结束后休息 atk_iv 秒。
                in_range = any(
                    (m.giant or abs(m.y - self.y) < 45) and
                    self.x - CELL_W * 0.5 <= m.x <= self.x + (self.melee_range + 0.5) * CELL_W
                    for m in ctx["monsters"])
                if in_range:
                    if self.atk_timer <= 0:
                        self.swing_timer = self.swing_sec * FPS
                        self.atk_timer = self.atk_iv * FPS
                    else:
                        self.atk_timer -= 1
                else:
                    self.atk_timer = 0
        # 罗格（2×3矩形横扫格斗者）：每 atk_iv 秒对 2×3 矩形内所有敌人造成范围伤害。
        # 基础罗格：物理劈砍；罗格SP：按当前形态（火/冰/毒）替换为元素伤害 + 附加状态，
        # 且普攻命中后 50% 概率触发【三行裂斩】——对自身行±1行整行所有敌人造成高额元素伤害。
        if self.behavior == "rog":
            # 锁敌范围：基础罗格 = 前方2格×当前行上下两行的 2×3 矩形；
            # SP烬 = 自身行±1行（三行整行），普攻横扫整行所有敌人（远处够不到也锁定）。
            if self.is_sp:
                in_rog = lambda m: (m.giant or abs(m.y - self.y) < CELL_H * 1.5)
            else:
                in_rog = lambda m: (m.giant or abs(m.y - self.y) < CELL_H * 1.5) and \
                                   self.x - CELL_W * 0.5 <= m.x <= self.x + (self.rog_range + 0.5) * CELL_W
            if self.atk_timer > 0:
                self.atk_timer -= 1
            else:
                targets = [m for m in ctx["monsters"][:] if in_rog(m)]
                self.rog_hit_this = bool(targets)
                if targets:
                    # 普攻元素专属特效：基础2×3横扫；SP烬覆盖三行整行（火带火焰/冰带冰刺/毒带毒液/基础带物理尖刺）
                    atk_mode = ("fire", "ice", "poison")[self.rog_form] if self.is_sp else "physical"
                    fx_w = ((self.rog_range + 8) * CELL_W if self.is_sp else 3 * CELL_W)
                    ctx["scene"].rog_slash_fx.append(
                        RogRowFx(self.x - CELL_W * 0.5, self.y - CELL_H * 1.5,
                                 fx_w, 3 * CELL_H, atk_mode))
                    if self.is_sp:
                        elem = ("fire", "ice", "poison")[self.rog_form]
                        for m in targets:
                            self.hit_monster(ctx, m, self.attack, elem)
                            if self.rog_form == 0:      # 火：附带灼烧（每秒12×层，3秒，可叠加）
                                m.burn_dmg = m.burn_dmg + 12
                                m.burn_timer = 3 * FPS
                                m.burn_attrs = self.atk_snapshot()
                            elif self.rog_form == 1:    # 冰：hit_monster(ice) 已附加寒冷5秒（移速/攻速-40%）
                                pass
                            elif self.rog_form == 2:    # 毒：附加腐蚀（每秒20毒伤/层、防御-18%/层，最多3层）
                                m.poison_stack = min(3, m.poison_stack + 1)
                                m.poison_dmg = 20
                                m.poison_timer = 5 * FPS
                                m.poison_attrs = self.atk_snapshot()
                                m.defense = m.base_defense * (1 - 0.18 * m.poison_stack)
                            if m.hp <= 0:
                                m.die(ctx["scene"])
                        # 全域斩击被动：普攻命中后50%触发三行裂斩（自身行±1行整行）
                        if self.rog_hit_this and random.random() < 0.5:
                            for mm in ctx["monsters"][:]:
                                if mm.giant or abs(mm.y - self.y) < CELL_H * 1.5:
                                    if self.rog_form == 0:
                                        self.hit_monster(ctx, mm, 500, "fire")
                                    elif self.rog_form == 1:
                                        self.hit_monster(ctx, mm, 500, "ice")
                                        mm.freeze_timer = max(mm.freeze_timer, int(1.5 * FPS))
                                        mm.cold_timer = max(mm.cold_timer, 5 * FPS)
                                    elif self.rog_form == 2:
                                        self.hit_monster(ctx, mm, 300, "poison")
                                        mm.poison_stack = 3
                                        mm.poison_dmg = 20
                                        mm.poison_timer = 5 * FPS
                                        mm.poison_attrs = self.atk_snapshot()
                                        mm.defense = mm.base_defense * (1 - 0.18 * 3)
                                    if mm.hp <= 0:
                                        mm.die(ctx["scene"])
                            # 三行裂斩元素专属特效（火带火焰/毒带毒液/冰带冰刺，覆盖自身行±1行）
                            row_mode = ("fire", "ice", "poison")[self.rog_form]
                            ctx["scene"].rog_slash_fx.append(
                                RogRowFx(self.x - CELL_W * 0.5, self.y - CELL_H * 1.5,
                                         (self.rog_range + 8) * CELL_W, 3 * CELL_H, row_mode))
                            # 元素龙：沿自身行从罗格身上向场外飞过一整行
                            ctx["scene"].rog_slash_fx.append(
                                RogDragonFx(self.x - CELL_W * 0.2, self.y,
                                            (self.rog_range + 8) * CELL_W, row_mode))
                    else:
                        # 基础罗格：2×3物理劈砍
                        for m in targets:
                            self.hit_monster(ctx, m, self.attack, "physical")
                            if m.hp <= 0:
                                m.die(ctx["scene"])
                    self.atk_timer = self.atk_iv * FPS
        # 水元素单位（卡斯珀）：普通高压水流——每1.8秒横扫自身格+前方4格内所有敌人；
        # 卡斯珀SP·奔流浪涛——穿透整行所有敌人，并降低全体伤害抗性30%
        if self.behavior == "water" and self.attack:
            if self.is_sp:
                # ---- 卡斯珀SP 普攻：整行穿透 ----
                self.atk_timer -= 1
                if self.atk_timer <= 0:
                    self.atk_timer = self.atk_iv * FPS
                    targets = [m for m in ctx["monsters"]
                               if m.giant or abs(m.y - self.y) < 45]
                    if targets:
                        for m in targets[:]:
                            self.hit_monster(ctx, m, self.attack, "water")
                            # 降低全部伤害抗性30%（水浪侵蚀，3秒内有效，被后续攻击刷新）
                            m.res_cut = max(getattr(m, "res_cut", 0.0), 0.3)
                            m.res_cut_timer = 3 * FPS
                            if m.hp <= 0:
                                m.die(ctx["scene"])
                        # 整行贯穿水浪特效（从自身格铺到行最右，覆盖整行）
                        ctx["scene"].water_fx.append(
                            WaterWaveFx(self.x - CELL_W * 0.5, self.y,
                                        GRID_COLS * CELL_W - self.x + CELL_W * 1.5))
            elif self.ult_remain > 0:
                self.ult_tick += 1
                if self.ult_tick >= FPS:
                    self.ult_tick = 0
                    self.ult_remain -= 1
                    for m in ctx["monsters"][:]:
                        if (m.giant or abs(m.y - self.y) < 45) and self.x - CELL_W * 0.5 <= m.x <= self.x + (self.melee_range + 0.5) * CELL_W:
                            self.hit_monster(ctx, m, self.ult, "water")
                            # 缓慢击退：在一段时间内缓缓推到4格后；
                            # 上限 = 卡斯珀前方第5格的前面边缘（=攻击范围右边界），而非"当前位置+4格"
                            kb_limit = self.x + (self.melee_range + 0.5) * CELL_W
                            m.kb_x = min(m.x + CELL_W * 4, kb_limit)
                            m.kb_speed = CELL_W * 4 / 54   # 约0.9秒推完4格
                            if m.hp <= 0:
                                m.die(ctx["scene"])
                    ctx["scene"].whirl_fx.append(
                        WhirlpoolFx(self.x + CELL_W * 0.5, self.y, (self.melee_range + 0.5) * CELL_W))
            else:
                self.atk_timer -= 1
                if self.atk_timer <= 0:
                    self.atk_timer = self.atk_iv * FPS
                    targets = [m for m in ctx["monsters"]
                               if (m.giant or abs(m.y - self.y) < 45)
                               and self.x - CELL_W * 0.5 <= m.x <= self.x + (self.melee_range + 0.5) * CELL_W]
                    if targets:
                        for m in targets[:]:
                            self.hit_monster(ctx, m, self.attack, "water")
                            if m.hp <= 0:
                                m.die(ctx["scene"])
                        ctx["scene"].water_fx.append(
                            WaterWaveFx(self.x, self.y, (self.melee_range + 0.5) * CELL_W))
        # 狙击单位（瓦伦丁）：定点狙杀——每5秒攻击全场血量最高的敌人（全屏、瞬间命中）
        if self.behavior == "sniper" and self.attack:
            self.atk_timer -= 1
            if self.atk_timer <= 0 and ctx["monsters"]:
                self.atk_timer = self.atk_iv * FPS      # 冷却从射击完成开始计算
                target = max(ctx["monsters"], key=lambda m: m.hp)
                self._snipe(ctx, target)
                self.sniper_shots += 1
                if self.sniper_ult > 0 and self.sniper_shots % 2 == 0:
                    # 战术再部署：每2次攻击额外再狙杀一次（重新锁定当前血量最高敌人）
                    t2 = max(ctx["monsters"], key=lambda m: m.hp) if ctx["monsters"] else None
                    if t2 is not None:
                        self._snipe(ctx, t2)
            if self.sniper_ult > 0:
                self.sniper_ult -= 1
                if self.sniper_ult <= 0:
                    self.sniper_shots = 0
        # 增益单位（埃利奥特）：振奋和弦常驻光环——3×3范围内友方攻击力+50%（可叠加）
        # 每帧累加覆盖光环数 _in_ell_rings，由场景在全部单位行动后统一汇总为 0.5×光环数
        if self.behavior == "buffer":
            for d in ctx["defenders"]:
                if d.hp <= 0:
                    continue
                if abs(d.x - self.x) < CELL_W * 1.5 and abs(d.y - self.y) < CELL_H * 1.5:
                    d._in_ell_rings += 1
        # 增益单位（赫利俄）：聚能棱镜——对正前方一格友方常驻提供暴击率+80%、爆伤+100%
        # 赫利俄被击倒/撤离时增益直接消失（由目标每帧校验来源是否仍存活实现）
        if self.behavior == "helio":
            for d in ctx["defenders"]:
                if d is self or d.hp <= 0:
                    continue
                # 正前方一格：同一行（y 相近）且 x 位于 self.x + 一个格子内
                if abs(d.y - self.y) < CELL_H * 0.6 and self.x + CELL_W * 0.5 <= d.x <= self.x + CELL_W * 1.5:
                    d.buff_crit_rate = 0.8
                    d.buff_crit_dmg = 1.0
                    d.buff_helio_x = self.x
        # 治疗单位（茯苓）：包扎——每秒为自身格及相邻一格（十字范围）友方回复生命
        if self.behavior == "healer":
            self.heal_timer -= 1
            if self.heal_timer <= 0:
                self.heal_timer = self.heal_iv * FPS
                for d in ctx["defenders"]:
                    dx = d.x - self.x
                    dy = d.y - self.y
                    # 十字范围：自身格 + 上下左右相邻一格
                    cross = ((abs(dx) <= CELL_W * 1.2 and abs(dy) <= CELL_H * 0.6) or
                             (abs(dx) <= CELL_W * 0.6 and abs(dy) <= CELL_H * 1.2))
                    if cross and d.hp > 0 and d.hp < d.maxhp:
                        d.hp = min(d.maxhp, d.hp + self.heal)
                        ctx["scene"].fx.append(FloatingText(d.x, d.y - 30, f"+{int(self.heal)}", (120, 220, 120), 13))
        # 治疗SP（茯苓SP）：愈光投瓶——每3秒锁定全场非满血友方（优先血量最低），落点3×3回复120
        #   并施加30%全属性增伤8秒；若没有残血友方则不释放（不会空放）
        elif self.behavior == "healer_sp":
            self.heal_timer -= 1
            if self.heal_timer <= 0:
                injured = [d for d in ctx["defenders"]
                           if d.hp > 0 and d.hp < d.maxhp]
                if injured:
                    self.heal_timer = self.heal_iv * FPS
                    target = min(injured, key=lambda d: d.hp)   # 锁定全场血量最低的友方
                    healed_any = False
                    for d in ctx["defenders"]:
                        if d.hp <= 0:
                            continue
                        # 以落点（目标格）为圆心、半径1.5格，圆形覆盖约3×3范围的友方都生效
                        dx = (d.x - target.x) / CELL_W
                        dy = (d.y - target.y) / CELL_H
                        if math.hypot(dx, dy) <= 1.5:
                            d.hp = min(d.maxhp, d.hp + self.heal)
                            d.buff_dmg_inc = max(d.buff_dmg_inc, self.heal_buff)   # 30%全属性增伤
                            d.buff_dmg_inc_timer = max(d.buff_dmg_inc_timer, self.heal_buff_sec * FPS)
                            ctx["scene"].fx.append(
                                FloatingText(d.x, d.y - 30, f"+{int(self.heal)}", (120, 220, 120), 13))
                            healed_any = True
                    if healed_any:
                        # 投瓶落地：绿色愈光药雾闪光
                        ctx["scene"].fx.append(
                            ParticleFx(target.x, target.y, (150, 240, 170), 16))
                else:
                    self.heal_timer = 0   # 无残血：不释放，下帧继续查（有残血立即投）
        # 持续回复（茯苓急救喷雾后续效果：每秒50，持续4秒）
        if self.hot_timer > 0 and self.hp > 0:
            self.hot_timer -= 1
            if self.hot_timer % FPS == 0:
                self.hp = min(self.maxhp, self.hp + self.hot_hp)
                ctx["scene"].fx.append(FloatingText(self.x, self.y - 30, f"+{int(self.hot_hp)}", (120, 220, 120), 13))
        self.anim_t += 1             # 动画帧计数（光环脉动等）
        # 增益状态计时（埃利奥特光环/大招）：到期后攻加回落
        if self.buff_dmg_inc_timer > 0:
            self.buff_dmg_inc_timer -= 1
            if self.buff_dmg_inc_timer <= 0:
                self.buff_dmg_inc = 0.0
        if self.buff_atk_timer > 0:
            self.buff_atk_timer -= 1
            if self.buff_atk_timer <= 0:
                self.buff_atk = 0.0
        if self.buff_atk_ult_timer > 0:
            self.buff_atk_ult_timer -= 1
            if self.buff_atk_ult_timer <= 0:
                self.buff_atk_ult = 0.0
        # 赫利俄聚能棱镜来源校验：来源赫利俄已被击倒/撤离（不再存活）→ 增益直接消失
        if self.buff_helio_x is not None:
            alive = any(d is not self and d.behavior == "helio" and d.hp > 0
                        and abs(d.x - self.buff_helio_x) < CELL_W * 0.5
                        for d in ctx["defenders"])
            if not alive:
                self.buff_crit_rate = 0.0
                self.buff_crit_dmg = 0.0
                self.buff_helio_x = None
        # 聚能棱镜负面代价：受加持（buff_crit_rate>0）的单位每5秒扣10点血。
        # 恒光刻印大招不再豁免扣血：大招后该单位仍持续扣血（保底1血不致死）；
        # 赫利俄离场增益消失则扣血停止
        if self.buff_crit_rate > 0:
            self.prism_bleed_timer -= 1
            if self.prism_bleed_timer <= 0:
                self.prism_bleed_timer = 5 * FPS
                self.hp = max(1, self.hp - 10)     # 保底1血：增益代价不直接杀死目标
                ctx["scene"].fx.append(FloatingText(self.x, self.y - 30, "-10", (210, 90, 90), 13))
        # 大招冷却
        if self.ult_cd > 0:
            self.ult_cd -= 1
        # 嘲讽计时（布洛克）：结束后护盾消失
        if self.taunt_timer > 0:
            self.taunt_timer -= 1
            if self.taunt_timer <= 0:
                self.shield = 0
        # 无敌计时（白夜SP永夜）：结束后恢复可被攻击
        if self.invuln_timer > 0:
            self.invuln_timer -= 1

    # ---- 绘制（普通 / SP 外观区分 + 血条）----
    def draw(self, screen):
        self.core_light = (self.core_light + 0.05) % 360
        if self.behavior == "energy":
            self._draw_leon(screen)
        elif self.behavior == "shooter":
            self._draw_kain(screen)
        elif self.behavior == "blocker":
            self._draw_brock(screen)
        elif self.behavior == "fire":
            self._draw_ignis(screen)
        elif self.behavior == "ice":
            self._draw_baiye(screen)
        elif self.behavior == "healer":
            self._draw_fuling(screen)
        elif self.behavior == "healer_sp":
            self._draw_fuling_sp(screen)
        elif self.behavior == "pierce":
            self._draw_cong(screen)
        elif self.behavior == "chain":
            self._draw_leonardo(screen)
        elif self.behavior == "water":
            self._draw_casper(screen)
        elif self.behavior == "sniper":
            self._draw_valentin(screen)
        elif self.behavior == "buffer":
            self._draw_elliott(screen)
        elif self.behavior == "helio":
            self._draw_helio(screen)
        elif self.behavior == "rog":
            self._draw_rog(screen)
        elif self.behavior == "mo":
            self._draw_mo(screen)
        elif self.behavior == "rena":
            self._draw_rena(screen)
        else:
            self._draw_nova(screen)
        # 恒光刻印标记：被刻印目标头顶金色菱形微光（不随赫利俄离场消失）
        if self.eternal_seal:
            pygame.draw.polygon(screen, COLOR_GOLD,
                                [(self.x, self.y - 41), (self.x + 5, self.y - 36),
                                 (self.x, self.y - 31), (self.x - 5, self.y - 36)])
            pygame.draw.circle(screen, (255, 235, 180), (self.x, self.y - 36), 2)
        # 聚能棱镜增益：受赫利俄常驻加持的目标脚下金色小光环
        if self.buff_crit_rate > 0:
            pygame.draw.circle(screen, (255, 220, 120), (self.x, self.y + 20), 9, 1)
            pygame.draw.circle(screen, (255, 240, 200), (self.x, self.y + 20), 5, 1)
        # 血条（火元素无生命值，不显示血条；卡片图标模式也不显示）
        if self.behavior != "fire" and not getattr(self, "icon_mode", False):
            rate = self.hp / self.maxhp
            pygame.draw.rect(screen, (80, 80, 80), (self.x - 20, self.y - 34, 40, 5))
            pygame.draw.rect(screen, COLOR_GREEN, (self.x - 20, self.y - 34, 40 * max(rate, 0), 5))

    def _draw_leon(self, screen):
        if self.is_sp:
            # SP：金色光环 + 头顶菱形 + 更大核心
            pygame.draw.circle(screen, (255, 200, 60), (self.x, self.y - 3), 32, 2)
            pygame.draw.polygon(screen, COLOR_GOLD, [(self.x-9, self.y-24), (self.x, self.y-35), (self.x+9, self.y-24)])
            pygame.draw.rect(screen, (248, 248, 252), (self.x-18, self.y-22, 38, 48), border_radius=8)
            pygame.draw.circle(screen, COLOR_GOLD, (self.x+2, self.y-9), 5)
            r = 12 + 3 * abs(math.sin(self.core_light))
            pygame.draw.circle(screen, COLOR_CORE, (self.x-14, self.y+4), r)
        else:
            pygame.draw.rect(screen, (235, 235, 240), (self.x-17, self.y-22, 35, 45), border_radius=8)
            pygame.draw.circle(screen, COLOR_GOLD, (self.x+1, self.y-9), 4)
            r = 8 + 2 * abs(math.sin(self.core_light))
            pygame.draw.circle(screen, COLOR_CORE, (self.x-13, self.y+3), r)

    def _draw_kain(self, screen):
        if self.is_sp:
            # SP：红橙光环 + 深灰重甲 + 大型双管投掷器
            pygame.draw.circle(screen, (255, 120, 40), (self.x, self.y - 2), 30, 2)
            pygame.draw.rect(screen, (70, 66, 58), (self.x-17, self.y-22, 38, 48), border_radius=6)
            pygame.draw.rect(screen, (150, 60, 40), (self.x-21, self.y-18, 42, 6))
            pygame.draw.rect(screen, COLOR_BROWN, (self.x-14, self.y-20, 22, 12))
            pygame.draw.circle(screen, (255, 60, 60), (self.x+4, self.y-11), 5)
            pygame.draw.rect(screen, (40, 40, 40), (self.x+4, self.y-16, 12, 24))
            pygame.draw.rect(screen, (255, 80, 40), (self.x+10, self.y-18, 4, 6))
        else:
            pygame.draw.rect(screen, COLOR_OLIVE, (self.x-17, self.y-22, 35, 45), border_radius=6)
            pygame.draw.rect(screen, COLOR_BROWN, (self.x-14, self.y-22, 22, 12))
            pygame.draw.circle(screen, (220, 220, 220), (self.x+4, self.y-13), 3)
            pygame.draw.rect(screen, (30, 30, 30), (self.x+8, self.y-15, 10, 20))

    def _draw_brock(self, screen):
        # 布洛克：钢板胸甲 + 轮毂肩甲 + 卡车门板大盾（左眉刀疤）
        # 头部
        pygame.draw.circle(screen, (150, 128, 110), (self.x, self.y - 30), 9)
        pygame.draw.line(screen, (90, 60, 50), (self.x - 7, self.y - 34), (self.x - 2, self.y - 31), 2)
        # 轮毂肩甲（两侧）
        for sx in (-22, 22):
            pygame.draw.circle(screen, (60, 60, 68), (self.x + sx, self.y - 14), 8)
            pygame.draw.circle(screen, (38, 38, 44), (self.x + sx, self.y - 14), 3)
        # 钢板胸甲（带中线）
        pygame.draw.rect(screen, (118, 126, 138), (self.x - 16, self.y - 10, 32, 32), border_radius=4)
        pygame.draw.line(screen, (88, 96, 108), (self.x, self.y - 10), (self.x, self.y + 22), 2)
        # 大盾（左手侧，卡车门板 + 刮痕）
        pygame.draw.rect(screen, (96, 100, 106), (self.x - 36, self.y - 18, 14, 38), border_radius=3)
        pygame.draw.line(screen, (70, 74, 80), (self.x - 32, self.y - 13), (self.x - 32, self.y + 13), 1)
        pygame.draw.line(screen, (70, 74, 80), (self.x - 27, self.y - 11), (self.x - 27, self.y + 11), 1)
        # 嘲讽中：红色外环；护盾：蓝色外环
        if self.taunt_timer > 0:
            pygame.draw.circle(screen, (255, 70, 60), (self.x, self.y - 2), 38, 2)
        if self.shield > 0:
            pygame.draw.circle(screen, (80, 170, 255), (self.x, self.y - 2), 31, 2)

    def _draw_ignis(self, screen):
        # 伊格尼斯：白色实验大褂 + 火红短发 + 腰间燃烧瓶（引信闪烁）
        pygame.draw.rect(screen, (235, 235, 240), (self.x - 17, self.y - 22, 35, 45), border_radius=8)
        pygame.draw.rect(screen, (210, 60, 40), (self.x - 12, self.y - 26, 24, 10), border_radius=4)   # 火红短发
        pygame.draw.rect(screen, (180, 90, 70), (self.x - 16, self.y - 6, 32, 4))                      # 焦痕
        # 举起燃烧瓶
        pygame.draw.rect(screen, (120, 90, 50), (self.x + 12, self.y - 14, 6, 16))
        pygame.draw.circle(screen, (255, 180, 60), (self.x + 15, self.y - 16), 4)
        # 引信闪烁（投掷倒计时）
        if self.fuse_timer % 6 < 3:
            pygame.draw.circle(screen, (255, 90, 30), (self.x + 15, self.y - 20), 3)

    def _draw_mo(self, screen):
        # 沫：浅亚麻短发呆毛 + 拼接旧防护服 + 胸口蓝色破损核心 + 双手捧储能罐
        pygame.draw.rect(screen, (150, 160, 150), (self.x - 16, self.y - 20, 32, 42), border_radius=8)   # 拼接防护服
        pygame.draw.rect(screen, (200, 190, 170), (self.x - 10, self.y - 26, 20, 8), border_radius=3)   # 浅亚麻短发
        pygame.draw.circle(screen, (200, 190, 170), (self.x, self.y - 30), 3)                            # 呆毛
        # 胸口蓝色破损能量核心（呼吸微光）
        pulse = 170 + int(50 * (0.5 + 0.5 * math.sin(self.core_light * 0.1)))
        pygame.draw.circle(screen, (pulse, pulse + 30, 255), (self.x, self.y - 8), 6)
        pygame.draw.circle(screen, (120, 130, 255), (self.x, self.y - 8), 3)
        # 双手捧着储能罐（罐体泛蓝光）
        pygame.draw.rect(screen, (90, 110, 130), (self.x - 5, self.y + 6, 11, 14), border_radius=3)
        pygame.draw.rect(screen, (160, 190, 255), (self.x - 3, self.y + 8, 7, 4))
        # 裤腿两侧挂着小电池
        pygame.draw.rect(screen, (70, 120, 90), (self.x - 15, self.y + 14, 4, 8))
        pygame.draw.rect(screen, (70, 120, 90), (self.x + 11, self.y + 14, 4, 8))

    def _draw_rena(self, screen):
        # 雷纳：深棕束发 + 暗黑防爆工装 + 胸/腰挂炸药包 + 手持起爆器 + 头顶护目镜
        pygame.draw.rect(screen, (55, 50, 48), (self.x - 17, self.y - 22, 35, 46), border_radius=6)     # 暗黑工装
        pygame.draw.rect(screen, (90, 60, 45), (self.x - 12, self.y - 27, 25, 9), border_radius=3)       # 深棕束发
        pygame.draw.rect(screen, (90, 60, 45), (self.x + 6, self.y - 27, 4, 7))                          # 束发马尾
        # 脸上浅浅灼伤疤痕（左颊一道短线）
        pygame.draw.line(screen, (200, 160, 150), (self.x - 5, self.y - 12), (self.x - 2, self.y - 8), 2)
        # 头顶推到额头的护目镜
        pygame.draw.rect(screen, (180, 190, 200), (self.x - 9, self.y - 31, 18, 5), border_radius=2)
        # 胸前挂满炸药包
        pygame.draw.rect(screen, (140, 100, 60), (self.x - 9, self.y - 6, 18, 7), border_radius=2)
        pygame.draw.circle(screen, (80, 70, 60), (self.x - 6, self.y - 5), 2)
        pygame.draw.circle(screen, (80, 70, 60), (self.x + 6, self.y - 5), 2)
        # 手持大型起爆器（引爆前红光闪烁）
        pygame.draw.rect(screen, (60, 60, 65), (self.x + 14, self.y - 10, 6, 18), border_radius=2)
        if self.life_timer > 0 and (self.life_timer // 6) % 2 == 0:
            pygame.draw.circle(screen, (255, 60, 40), (self.x + 17, self.y - 6), 3)     # 引爆待机警示灯

    def _draw_fuling(self, screen):
        # 茯苓：黑色齐耳短发+银夹子、米色连帽卫衣、深蓝百褶裙、白色医疗包（带小花）        pygame.draw.rect(screen, (200, 190, 170), (self.x - 16, self.y - 16, 32, 34), border_radius=9)   # 米色卫衣
        pygame.draw.rect(screen, (60, 70, 100), (self.x - 14, self.y + 14, 28, 12), border_radius=3)     # 深蓝百褶裙
        pygame.draw.rect(screen, (245, 245, 245), (self.x - 8, self.y + 26, 14, 4), border_radius=2)     # 白色运动鞋
        pygame.draw.circle(screen, (245, 240, 230), (self.x, self.y - 30), 10)                          # 脸
        # 黑色齐耳短发（头顶弧 + 发尾）
        pygame.draw.arc(screen, (30, 30, 35), (self.x - 11, self.y - 39, 22, 18), 0, 3.14, 4)
        pygame.draw.rect(screen, (30, 30, 35), (self.x - 11, self.y - 34, 22, 7), border_radius=4)
        # 银色小夹子
        pygame.draw.circle(screen, (215, 225, 235), (self.x - 8, self.y - 33), 2)
        pygame.draw.circle(screen, (215, 225, 235), (self.x + 8, self.y - 33), 2)
        # 白色医疗包（左肩，马克笔画的小花）
        pygame.draw.rect(screen, (245, 245, 245), (self.x - 23, self.y - 2, 14, 17), border_radius=4)
        pygame.draw.circle(screen, (255, 160, 160), (self.x - 16, self.y + 5), 3)
        # 手中药雾光团
        pygame.draw.circle(screen, (150, 235, 170), (self.x + 18, self.y), 6)

    def _draw_fuling_sp(self, screen):
        """茯苓SP：利落黑短发+浅绿玉饰、干净浅医护制服、白绿制式药箱、指尖药草微光。"""
        # 浅医护制服（白绿拼接）
        pygame.draw.rect(screen, (240, 248, 240), (self.x - 16, self.y - 16, 32, 34), border_radius=9)
        pygame.draw.rect(screen, (170, 225, 185), (self.x - 16, self.y + 2, 32, 14), border_radius=4)  # 绿围裙
        pygame.draw.rect(screen, (60, 80, 90), (self.x - 14, self.y + 14, 28, 12), border_radius=3)    # 深色束脚裤
        pygame.draw.rect(screen, (245, 245, 245), (self.x - 8, self.y + 26, 14, 4), border_radius=2)   # 白鞋
        pygame.draw.circle(screen, (245, 238, 228), (self.x, self.y - 30), 10)                         # 脸（清亮）
        # 利落黑色短发（短齐）
        pygame.draw.arc(screen, (25, 25, 30), (self.x - 11, self.y - 39, 22, 18), 0, 3.14, 4)
        pygame.draw.rect(screen, (25, 25, 30), (self.x - 11, self.y - 35, 22, 6), border_radius=4)
        # 浅绿玉饰发夹（取代银夹子）
        pygame.draw.circle(screen, (170, 230, 180), (self.x - 8, self.y - 33), 2)
        pygame.draw.circle(screen, (170, 230, 180), (self.x + 8, self.y - 33), 2)
        # 白绿制式药箱（带绿色十字）
        pygame.draw.rect(screen, (245, 250, 245), (self.x - 23, self.y - 2, 15, 18), border_radius=4)
        pygame.draw.line(screen, (90, 200, 120), (self.x - 19, self.y + 1), (self.x - 19, self.y + 13), 2)
        pygame.draw.line(screen, (90, 200, 120), (self.x - 25, self.y + 7), (self.x - 13, self.y + 7), 2)
        # 指尖药草微光
        pygame.draw.circle(screen, (170, 250, 190), (self.x + 18, self.y), 6)
        pygame.draw.circle(screen, (210, 255, 220), (self.x + 18, self.y), 3)

    def _draw_cong(self, screen):
        # 琮：深棕短发+小揪揪、银色圆框眼镜、灰绿风衣、黑色高领、细长电磁枪
        pygame.draw.rect(screen, (110, 130, 105), (self.x - 17, self.y - 20, 34, 44), border_radius=8)   # 灰绿风衣
        pygame.draw.rect(screen, (25, 28, 32), (self.x - 12, self.y - 12, 24, 20), border_radius=4)      # 黑色高领
        pygame.draw.circle(screen, (238, 230, 215), (self.x, self.y - 30), 10)                          # 脸
        pygame.draw.arc(screen, (70, 50, 30), (self.x - 11, self.y - 39, 22, 18), 0, 3.14, 4)            # 深棕短发
        pygame.draw.circle(screen, (70, 50, 30), (self.x + 9, self.y - 41), 4)                          # 后脑小揪揪
        # 银色圆框眼镜（带淡紫膜反光）
        pygame.draw.circle(screen, (220, 225, 235), (self.x - 4, self.y - 29), 4, 2)
        pygame.draw.circle(screen, (220, 225, 235), (self.x + 4, self.y - 29), 4, 2)
        pygame.draw.line(screen, (220, 225, 235), (self.x - 8, self.y - 29), (self.x + 8, self.y - 29), 1)
        # 半指皮手套（右手持枪）
        pygame.draw.rect(screen, (95, 70, 50), (self.x + 12, self.y - 6, 8, 14), border_radius=3)
        # 电磁贯通枪：细长枪管 + 枪身缠绝缘胶带
        pygame.draw.line(screen, (60, 65, 75), (self.x + 18, self.y - 4), (self.x + 46, self.y - 4), 5)
        pygame.draw.line(screen, (240, 240, 240), (self.x + 26, self.y - 8), (self.x + 40, self.y - 8), 2)
        # 枪口蓄能光点
        pygame.draw.circle(screen, (170, 220, 255), (self.x + 46, self.y - 4), 3)

    def _draw_nova(self, screen):
        # 诺瓦：深蓝工装连体裤 + 黄色雨靴 + 荧光涂鸦电锯（切割时锯条发光）
        # 大招（锯刃风暴）特效：前方4格高亮 + 旋转大圆锯沿路径推进
        if self.ult_remain > 0:
            ov = pygame.Surface((int(5.0 * CELL_W), 70), pygame.SRCALPHA)
            ov.fill((150, 220, 255, 30))
            screen.blit(ov, (int(self.x - CELL_W * 0.5), self.y - 35))
            prog = 5 - self.ult_remain          # 0→4：圆锯随段数推进
            sawx = self.x + CELL_W * 0.8 + prog * (CELL_W * 0.8)
            ang = self.core_light * 2
            pygame.draw.circle(screen, (200, 230, 255), (int(sawx), self.y), 26, 4)
            for k in range(8):
                a = math.radians(ang + k * 45)
                x2 = sawx + math.cos(a) * 30
                y2 = self.y + math.sin(a) * 30
                pygame.draw.line(screen, (235, 250, 255), (sawx, self.y), (x2, y2), 3)
            pygame.draw.circle(screen, (120, 160, 200), (int(sawx), self.y), 10)
        # 切割中：显示攻击范围特效（半透明高亮区 + 横向锯齿线动画），让玩家看清打的是哪一块
        elif self.swing_timer > 0:
            sx0 = int(self.x - CELL_W // 2)                     # 自身格左边界
            sw0 = int((self.melee_range + 1) * CELL_W)          # 自身格+前方3格（共4格宽）
            ov = pygame.Surface((sw0, 62), pygame.SRCALPHA)
            ov.fill((255, 200, 80, 36))
            screen.blit(ov, (sx0, self.y - 31))
            off = int((self.core_light * 3) % 34)
            for i in range(-34, sw0, 17):
                x0 = sx0 + i + off
                pygame.draw.line(screen, (255, 245, 160), (x0, self.y - 20), (x0 + 12, self.y + 12), 2)
        pygame.draw.rect(screen, (60, 90, 130), (self.x - 16, self.y - 22, 34, 45), border_radius=7)
        pygame.draw.circle(screen, (150, 160, 175), (self.x, self.y - 28), 9)      # 银灰短发脑袋
        pygame.draw.circle(screen, (255, 200, 120), (self.x + 3, self.y - 29), 2)   # 琥珀色瞳孔
        # 黄色雨靴
        pygame.draw.rect(screen, (210, 190, 60), (self.x - 14, self.y + 16, 12, 8), border_radius=3)
        pygame.draw.rect(screen, (210, 190, 60), (self.x + 4, self.y + 16, 12, 8), border_radius=3)
        # 电锯（前方）
        pygame.draw.rect(screen, (120, 120, 130), (self.x + 14, self.y - 16, 26, 12), border_radius=3)
        if self.swing_timer > 0:
            pygame.draw.rect(screen, (255, 240, 120), (self.x + 16, self.y - 15, 22, 4))   # 锯条亮起
            pygame.draw.circle(screen, (255, 240, 120), (self.x + 40, self.y - 10), 3)
        else:
            pygame.draw.rect(screen, (60, 60, 70), (self.x + 16, self.y - 15, 22, 4))
        # 荧光星星涂鸦
        pygame.draw.circle(screen, (120, 240, 200), (self.x + 22, self.y - 10), 2)

    def _draw_baiye(self, screen):
        if self.is_sp:
            # 白夜SP：银白长卷发低马尾 + 淡紫眼瞳 + 脸颊寒霜 + 灰蓝防寒风衣(衣摆冰棱) + 手臂低温装置 + 悬浮冰晶
            # 灰蓝防寒风衣（加厚风衣）
            pygame.draw.rect(screen, (96, 120, 150), (self.x - 16, self.y - 20, 32, 42), border_radius=6)
            pygame.draw.rect(screen, (70, 96, 126), (self.x - 18, self.y - 14, 36, 30), border_radius=8)
            # 衣摆冰棱（底部尖角）
            for i in range(3):
                bx = self.x - 12 + i * 12
                pygame.draw.polygon(screen, (150, 205, 240),
                                    [(bx, self.y + 18), (bx + 6, self.y + 24), (bx + 12, self.y + 18)])
            # 银白长卷发（两侧卷发）+ 脸
            pygame.draw.circle(screen, (238, 236, 244), (self.x, self.y - 30), 10)   # 脸
            pygame.draw.circle(screen, (228, 230, 240), (self.x - 6, self.y - 33), 6)   # 卷发左
            pygame.draw.circle(screen, (228, 230, 240), (self.x + 5, self.y - 33), 6)   # 卷发右
            pygame.draw.rect(screen, (228, 230, 240), (self.x - 5, self.y - 22, 10, 18), border_radius=4)  # 低马尾垂落
            # 淡紫眼瞳
            pygame.draw.circle(screen, (170, 130, 220), (self.x + 3, self.y - 29), 2)
            pygame.draw.circle(screen, (170, 130, 220), (self.x - 5, self.y - 29), 2)
            # 脸颊寒霜痕迹
            pygame.draw.circle(screen, (200, 225, 245), (self.x - 7, self.y - 24), 2)
            # 左臂便携低温装置（发光）
            pygame.draw.rect(screen, (120, 160, 210), (self.x - 20, self.y - 4, 10, 12), border_radius=3)
            pygame.draw.circle(screen, (180, 225, 255), (self.x - 17, self.y + 2), 3)
            # 手中悬浮冰晶（旋转寒光）
            t = pygame.time.get_ticks()
            a = t / 140
            pygame.draw.polygon(screen, (190, 235, 255),
                                [(self.x + 16 + 5 * math.cos(a), self.y - 2 + 5 * math.sin(a)),
                                 (self.x + 16 + 5 * math.cos(a + 2.09), self.y - 2 + 5 * math.sin(a + 2.09)),
                                 (self.x + 16 + 5 * math.cos(a + 4.19), self.y - 2 + 5 * math.sin(a + 4.19))])
            return
        # 白夜（普通）：米白高领毛衣 + 浅灰羽绒马甲 + 银白长发（发尾浅蓝光晕）+ 雪花耳钉
        pygame.draw.rect(screen, (235, 232, 220), (self.x - 16, self.y - 20, 32, 42), border_radius=8)   # 米白毛衣
        pygame.draw.rect(screen, (200, 202, 210), (self.x - 18, self.y - 18, 36, 10), border_radius=5)   # 浅灰马甲
        # 银白长发（两侧垂落，发尾浅蓝光晕）
        pygame.draw.rect(screen, (225, 230, 240), (self.x - 20, self.y - 30, 8, 26), border_radius=3)
        pygame.draw.rect(screen, (225, 230, 240), (self.x + 12, self.y - 30, 8, 26), border_radius=3)
        pygame.draw.circle(screen, (180, 220, 245), (self.x - 22, self.y - 6), 2)
        pygame.draw.circle(screen, (180, 220, 245), (self.x + 14, self.y - 6), 2)
        pygame.draw.circle(screen, (245, 240, 230), (self.x, self.y - 30), 10)   # 脸
        # 红发绳 + 雪花耳钉
        pygame.draw.rect(screen, (220, 70, 60), (self.x - 5, self.y - 36, 10, 3))
        pygame.draw.circle(screen, (210, 230, 255), (self.x + 14, self.y - 26), 2)
        # 手中凝霜弹（浅蓝光团）
        pygame.draw.circle(screen, (160, 220, 255), (self.x + 16, self.y - 2), 5)


    def _draw_leonardo(self, screen):
        """莱昂纳多：灰白卷发、军绿工装夹克、肩挎信号收发器、右手金属导棍+蓝色陶瓷线圈。"""
        # 身体（军绿工装夹克）
        pygame.draw.rect(screen, (78, 96, 74), (self.x - 12, self.y - 14, 24, 34), border_radius=6)
        # 头（灰白卷发 + 脸 + 刘海遮眼）
        pygame.draw.circle(screen, (222, 214, 200), (self.x, self.y - 22), 10)
        pygame.draw.circle(screen, (196, 196, 196), (self.x - 6, self.y - 26), 5)
        pygame.draw.circle(screen, (196, 196, 196), (self.x + 5, self.y - 27), 5)
        pygame.draw.circle(screen, (196, 196, 196), (self.x + 1, self.y - 29), 4)
        pygame.draw.line(screen, (196, 196, 196), (self.x - 8, self.y - 22), (self.x - 12, self.y - 12), 3)
        pygame.draw.circle(screen, (165, 195, 215), (self.x + 3, self.y - 20), 2)   # 眼睛
        # 肩挎信号收发器（金属外壳 + 彩色电线）
        pygame.draw.rect(screen, (128, 118, 96), (self.x - 20, self.y - 4, 14, 16), border_radius=3)
        pygame.draw.line(screen, (230, 120, 60), (self.x - 18, self.y - 2), (self.x - 12, self.y + 8), 2)
        pygame.draw.line(screen, (90, 170, 230), (self.x - 14, self.y - 2), (self.x - 8, self.y + 8), 2)
        # 右手金属导棍 + 顶部蓝色陶瓷线圈（发光）
        pygame.draw.line(screen, (110, 120, 130), (self.x + 8, self.y + 6), (self.x + 22, self.y - 8), 4)
        pygame.draw.circle(screen, (110, 190, 255), (self.x + 22, self.y - 8), 4)
        pygame.draw.circle(screen, (205, 235, 255), (self.x + 22, self.y - 8), 2)

    def _draw_casper(self, screen):
        if self.is_sp:
            self._draw_casper_sp(screen)
            return
        """卡斯珀：深蓝及肩长发、湖绿眼、深灰高领风衣、右肩黄铜水压罐。"""
        # 身体（深灰高领风衣）
        pygame.draw.rect(screen, (72, 74, 84), (self.x - 12, self.y - 14, 24, 34), border_radius=6)
        # 头（深蓝长发 + 冷白脸 + 湖绿眼）
        pygame.draw.circle(screen, (218, 218, 224), (self.x, self.y - 22), 10)
        pygame.draw.circle(screen, (40, 62, 96), (self.x - 6, self.y - 26), 5)
        pygame.draw.circle(screen, (40, 62, 96), (self.x + 6, self.y - 27), 5)
        pygame.draw.circle(screen, (40, 62, 96), (self.x + 1, self.y - 29), 4)
        pygame.draw.line(screen, (40, 62, 96), (self.x - 9, self.y - 22), (self.x - 13, self.y - 10), 3)
        pygame.draw.circle(screen, (120, 200, 170), (self.x + 3, self.y - 20), 2)   # 湖绿眼
        # 右肩黄铜水压罐（表面凝结细密水珠）
        pygame.draw.rect(screen, (168, 138, 84), (self.x - 20, self.y - 2, 12, 20), border_radius=3)
        pygame.draw.circle(screen, (140, 200, 255), (self.x - 17, self.y + 2), 1)
        pygame.draw.circle(screen, (140, 200, 255), (self.x - 14, self.y + 8), 1)
        pygame.draw.circle(screen, (140, 200, 255), (self.x - 16, self.y + 13), 1)
        # 水流喷射（向前方斜线）
        pygame.draw.line(screen, (110, 200, 255), (self.x + 8, self.y - 2), (self.x + 24, self.y - 14), 3)

    def _draw_casper_sp(self, screen):
        """卡斯珀SP：更长的深蓝悬浮长发、湖绿泛水光眼、半透明风衣、扩容水压罐涌出水幕、周身水雾。"""
        # 周身细碎水雾（漂浮小水珠）
        for i, (ox, oy) in enumerate(((-18, -16), (16, -20), (-22, 8), (20, 10))):
            px = self.x + ox + int(math.sin(self.anim_t * 0.12 + i * 1.7) * 3)
            pygame.draw.circle(screen, (150, 210, 255), (px, self.y + oy), 2)
        # 深灰高领风衣（边缘半透明水流侵蚀：加半透明浅蓝描边）
        pygame.draw.rect(screen, (62, 66, 76), (self.x - 12, self.y - 14, 24, 34), border_radius=6)
        pygame.draw.rect(screen, (90, 160, 220), (self.x - 12, self.y - 14, 24, 34), 1, border_radius=6)
        # 头（冷白脸 + 湖绿泛水光眼 + 深蓝长卷发，发丝漂浮悬空）
        pygame.draw.circle(screen, (216, 216, 224), (self.x, self.y - 22), 10)
        # 漂浮悬空的长发：两侧拖出飘动发丝（比普通更长、随相位摆动）
        for side, sign in ((-1, -1), (1, 1)):
            pygame.draw.circle(screen, (30, 48, 84), (self.x + sign * 8, self.y - 26), 5)
            for h in range(3):
                sway = int(math.sin(self.anim_t * 0.12 + side + h) * 4)
                pygame.draw.line(screen, (34, 56, 96),
                                 (self.x + sign * 9, self.y - 20 + h * 8),
                                 (self.x + sign * (14 + sway), self.y - 6 + h * 8), 3)
        pygame.draw.circle(screen, (150, 220, 210), (self.x + 3, self.y - 20), 3)   # 湖绿泛水光眼
        # 扩容水压罐（右肩，更大，表面涌出水幕细线）
        pygame.draw.rect(screen, (158, 128, 78), (self.x - 21, self.y - 4, 14, 24), border_radius=3)
        pygame.draw.circle(screen, (140, 200, 255), (self.x - 18, self.y + 3), 1)
        pygame.draw.circle(screen, (140, 200, 255), (self.x - 15, self.y + 10), 1)
        pygame.draw.circle(screen, (140, 200, 255), (self.x - 17, self.y + 16), 1)
        # 罐体涌出的水幕：向前方延伸的水流带（贯穿整行的水线）
        for i in range(3):
            pygame.draw.line(screen, (120, 205, 255),
                             (self.x + 9, self.y - 2 + i * 3),
                             (self.x + 26, self.y - 12 + i * 3), 2)

    def _draw_elliott(self, screen):
        """埃利奥特：深棕卷发、琥珀眼、深蓝牛仔夹克、背发光电吉他。"""
        # 身体（深蓝牛仔夹克 + 黑色旧T恤）
        pygame.draw.rect(screen, (58, 78, 128), (self.x - 12, self.y - 14, 24, 34), border_radius=6)
        pygame.draw.rect(screen, (40, 42, 48), (self.x - 7, self.y - 8, 14, 20), border_radius=3)
        # 头（深棕卷发 + 暖调脸 + 琥珀眼）
        pygame.draw.circle(screen, (228, 210, 190), (self.x, self.y - 22), 10)
        pygame.draw.circle(screen, (104, 74, 52), (self.x - 6, self.y - 27), 6)
        pygame.draw.circle(screen, (104, 74, 52), (self.x + 6, self.y - 26), 5)
        pygame.draw.line(screen, (104, 74, 52), (self.x - 10, self.y - 20), (self.x - 13, self.y - 10), 3)
        pygame.draw.circle(screen, (230, 170, 70), (self.x + 3, self.y - 20), 2)   # 琥珀眼
        # 左耳银耳环 + 红色宝石
        pygame.draw.circle(screen, (215, 215, 225), (self.x - 11, self.y - 16), 2)
        pygame.draw.circle(screen, (220, 70, 60), (self.x - 11, self.y - 14), 1)
        # 电吉他（琴身 + 发光增幅器）
        pygame.draw.rect(screen, (120, 60, 50), (self.x + 6, self.y - 12, 10, 26), border_radius=3)
        pygame.draw.line(screen, (90, 80, 70), (self.x + 12, self.y - 14), (self.x + 16, self.y - 6), 2)
        pygame.draw.circle(screen, (110, 220, 255), (self.x + 8, self.y - 8), 2)   # 发光增幅器
        pygame.draw.circle(screen, (210, 245, 255), (self.x + 8, self.y - 8), 1)
        # ---- 常驻光环特效：振奋和弦（3×3范围声波光圈 + 音符漂浮）----
        if not getattr(self, "icon_mode", False):
            t = self.anim_t
            pulse = 0.5 + 0.5 * math.sin(t * 0.05)
            w3, h3 = CELL_W * 3, CELL_H * 3
            aura = pygame.Surface((w3, h3), pygame.SRCALPHA)
            pygame.draw.rect(aura, (190, 130, 235, int(50 + 40 * pulse)),
                             aura.get_rect(), 2, border_radius=14)
            screen.blit(aura, (int(self.x - w3 * 0.5), int(self.y - h3 * 0.5)))
            # 脚下声波圆环脉动
            r = 16 + int(4 * pulse)
            pygame.draw.circle(screen, (205, 145, 240), (int(self.x), int(self.y + 18)), r, 2)
            pygame.draw.circle(screen, (235, 190, 255), (int(self.x), int(self.y + 18)), r - 6, 1)
            # 音符粒子在光环内漂浮
            for i in range(3):
                ang = t * 0.02 + i * 2.09
                nx = self.x + math.cos(ang) * (12 + 5 * i)
                ny = self.y - 10 + math.sin(t * 0.03 + i * 1.7) * 8
                pygame.draw.rect(screen, (220, 170, 250), (int(nx - 2), int(ny - 2), 4, 4))
                pygame.draw.circle(screen, (220, 170, 250), (int(nx + 2), int(ny - 3)), 2)

    def _draw_helio(self, screen):
        """赫利俄：浅金短发发丝微光、橙金瞳、光学护目镜、浅卡其科研服+橙色战术胸挂、
           胸前大型聚能棱镜装置随充能发光；常驻对正前方一格射出一道金色棱镜光线。"""
        x, y = self.x, self.y
        t = self.anim_t
        pulse = 0.5 + 0.5 * math.sin(t * 0.07)
        glow = int(120 + 110 * pulse)
        # 胸前聚能棱镜装置（发光菱形，随充能脉动）
        pygame.draw.polygon(screen, (glow, 190, 90),
                            [(x - 8, y - 2), (x, y - 8), (x + 8, y - 2), (x, y + 6)])
        pygame.draw.polygon(screen, (255, 240, 200),
                            [(x - 4, y - 1), (x, y - 4), (x + 4, y - 1), (x, y + 3)])
        # 身体（浅卡其科研防护服 + 橙色战术胸挂）
        pygame.draw.rect(screen, (200, 186, 150), (x - 12, y - 12, 24, 32), border_radius=6)
        pygame.draw.rect(screen, (235, 140, 60), (x - 9, y - 8, 18, 8), border_radius=3)
        # 头（浅金色短发，发丝边缘带微光）
        pygame.draw.circle(screen, (232, 214, 186), (x, y - 22), 10)
        pygame.draw.circle(screen, (245, 205, 125), (x - 6, y - 27), 6)
        pygame.draw.circle(screen, (245, 205, 125), (x + 6, y - 26), 5)
        # 光学护目镜（橙色横带镜片）
        pygame.draw.rect(screen, (56, 56, 66), (x - 9, y - 24, 18, 6), border_radius=3)
        pygame.draw.circle(screen, (255, 170, 70), (x + 3, y - 22), 2)   # 橙金眼
        # 脖颈能量调节器
        pygame.draw.rect(screen, (110, 110, 122), (x - 3, y - 12, 6, 4))
        # ---- 常驻棱镜光线：正前方一格射向友方（金色光束 + 目标光斑）----
        if not getattr(self, "icon_mode", False):
            tx = x + CELL_W
            pygame.draw.line(screen, (glow, 190, 100), (x + 10, y - 2), (int(tx) - 8, y - 2), 2)
            pygame.draw.circle(screen, (255, 230, 160), (int(tx) - 8, y - 2), int(3 + 2 * pulse))

    def _draw_rog(self, screen):
        """荒龙·罗格（龙裔形态）：深黑短发、眉骨刀疤、黑色皮质护具、龙角、背后龙翼、
           刀身龙纹、钢板肩甲；SP三元素形态按当前形态换色（火红/冰蓝/毒绿）+ 头顶形态标签。"""
        x, y = self.x, self.y
        if self.is_sp:
            if self.rog_form == 0:        # 火：炽焰征伐（火红甲、刀身火焰、火龙角）
                col, acc, glow = (150, 50, 40), (255, 150, 60), (255, 200, 90)
                label, lc = "火", DAMAGE_COLOR_FIRE
            elif self.rog_form == 1:      # 冰：霜狱禁锢（冰蓝甲、刀身寒霜、冰龙角）
                col, acc, glow = (70, 110, 150), (140, 210, 255), (190, 240, 255)
                label, lc = "冰", DAMAGE_COLOR_ICE
            else:                         # 毒：腐毒蚀骨（暗绿甲、刀身腐蚀液、毒龙角）
                col, acc, glow = (80, 120, 60), (170, 225, 110), (200, 240, 130)
                label, lc = "毒", DAMAGE_COLOR_POISON
        else:
            col, acc, glow = (46, 44, 48), (120, 116, 124), (150, 148, 156)
            label, lc = "物", DAMAGE_COLOR_PHYS
        # 背后龙翼（左右各一片，向后张开，元素色边缘）
        pygame.draw.polygon(screen, acc,
                            [(x - 10, y - 4), (x - 26, y - 16), (x - 22, y - 4), (x - 10, y + 2)])
        pygame.draw.line(screen, glow, (x - 24, y - 13), (x - 12, y - 1), 2)
        pygame.draw.polygon(screen, acc,
                            [(x + 10, y - 4), (x + 26, y - 16), (x + 22, y - 4), (x + 10, y + 2)])
        pygame.draw.line(screen, glow, (x + 24, y - 13), (x + 12, y - 1), 2)
        # 头（深黑短发 + 眉骨刀疤）
        pygame.draw.circle(screen, (222, 205, 185), (x, y - 22), 10)
        pygame.draw.circle(screen, (30, 28, 30), (x - 6, y - 27), 6)
        pygame.draw.circle(screen, (30, 28, 30), (x + 6, y - 26), 5)
        pygame.draw.line(screen, (120, 90, 80), (x + 6, y - 23), (x + 9, y - 20), 2)   # 眉骨刀疤
        # 龙角：头顶两侧向后上方弯曲的角（元素色），龙裔标志
        pygame.draw.polygon(screen, glow,
                            [(x - 8, y - 29), (x - 16, y - 42), (x - 6, y - 32)])
        pygame.draw.polygon(screen, glow,
                            [(x + 8, y - 29), (x + 16, y - 42), (x + 6, y - 32)])
        # 身体（黑色皮质护具 + 龙鳞纹 + 钢板肩甲）
        pygame.draw.rect(screen, col, (x - 12, y - 12, 24, 32), border_radius=5)
        pygame.draw.rect(screen, (92, 96, 104), (x - 15, y - 14, 7, 7), border_radius=2)   # 左肩甲
        pygame.draw.rect(screen, (92, 96, 104), (x + 8, y - 14, 7, 7), border_radius=2)    # 右肩甲
        # 胸前龙鳞纹（两排菱形小鳞片，元素高光色）
        for i, sy in enumerate((y - 6, y - 1, y + 4)):
            pygame.draw.polygon(screen, glow,
                                [(x - 8 + (i % 2) * 4, sy), (x - 3 + (i % 2) * 4, sy + 3), (x - 8 + (i % 2) * 4, sy + 6)])
        # 小臂加固绷带
        pygame.draw.rect(screen, (200, 190, 180), (x - 13, y + 2, 4, 8))
        pygame.draw.rect(screen, (200, 190, 180), (x + 9, y + 2, 4, 8))
        # 重型宽刃砍刀（右侧斜握，刃带元素光 + 刀身龙纹）
        pygame.draw.polygon(screen, (190, 192, 198),
                            [(x + 8, y + 16), (x + 22, y + 4), (x + 18, y - 4), (x + 4, y + 8)])
        pygame.draw.line(screen, glow, (x + 16, y + 6), (x + 8, y - 2), 2)
        pygame.draw.polygon(screen, glow,
                            [(x + 11, y + 2), (x + 14, y + 10), (x + 17, y + 3)])       # 刀身龙纹
        # 头顶形态标签（SP：元素图标块；基础：物理）
        pygame.draw.circle(screen, col, (x, y - 34), 7)
        pygame.draw.circle(screen, glow, (x, y - 34), 5)
        pygame.draw.line(screen, (20, 20, 24), (x, y - 37), (x, y - 31), 2)
        # 脚下光环按形态配色（常驻，提示当前形态）
        if not getattr(self, "icon_mode", False):
            r = 15 + int(2 * math.sin(self.anim_t * 0.06))
            pygame.draw.circle(screen, glow, (x, y + 20), r, 2)

    def _draw_valentin(self, screen):
        """瓦伦丁（帅版）：废土最强猎手——弓步架枪狙击姿态、棱角分明的下颌、
           向后梳理的灰褐背头、铁灰狭长冷眼、左眉弹片旧疤、立领战术内衬、
           深棕皮夹克分层光影 + 风衣下摆被风吹起、栓动步枪抵肩瞄准带镜片反光。"""
        x, y = self.x, self.y
        t = self.anim_t
        wave = int(2 * math.sin(t * 0.06))                       # 风衣下摆飘动
        # ---- 腿部：前弓步站姿（稳定的射击姿态） ----
        pygame.draw.rect(screen, (52, 42, 32), (x - 10, y + 2, 7, 13))     # 后腿
        pygame.draw.rect(screen, (66, 52, 38), (x + 2, y, 8, 15))          # 前腿弓步
        pygame.draw.rect(screen, (38, 34, 30), (x - 12, y + 14, 9, 4))     # 后靴
        pygame.draw.rect(screen, (38, 34, 30), (x + 2, y + 14, 10, 4))     # 前靴
        # ---- 风衣下摆（被风吹起，左右两层飘动） ----
        pygame.draw.polygon(screen, (98, 74, 50),
                            [(x - 13, y - 4), (x - 21, y + 15 + wave), (x - 9, y + 11)])
        pygame.draw.polygon(screen, (98, 74, 50),
                            [(x + 13, y - 4), (x + 22, y + 13 - wave), (x + 9, y + 9)])
        # ---- 身体：深棕皮夹克（左襟高光 + 右侧阴影分层，更立体） ----
        pygame.draw.rect(screen, (104, 76, 52), (x - 12, y - 20, 24, 24), border_radius=5)
        pygame.draw.rect(screen, (126, 92, 62), (x - 10, y - 20, 7, 24), border_radius=3)   # 左襟高光
        pygame.draw.rect(screen, (86, 62, 42), (x + 4, y - 18, 5, 18))                       # 右侧阴影
        # 皮夹克翻领（V字立领）
        pygame.draw.polygon(screen, (88, 62, 42),
                            [(x - 12, y - 18), (x - 5, y - 10), (x - 12, y - 9)])
        pygame.draw.polygon(screen, (88, 62, 42),
                            [(x + 12, y - 18), (x + 5, y - 10), (x + 12, y - 9)])
        # 灰绿高领战术内衬（立领，比夹克高出一截）
        pygame.draw.rect(screen, (86, 100, 82), (x - 7, y - 26, 14, 9), border_radius=3)
        pygame.draw.line(screen, (126, 146, 118), (x - 5, y - 25), (x - 5, y - 18), 2)      # 领口高光
        # ---- 头：棱角分明的下颌轮廓（多边形，比之前更成熟硬朗） ----
        pygame.draw.polygon(screen, (198, 180, 164),
                            [(x, y - 34), (x - 8, y - 27), (x - 6, y - 20), (x + 6, y - 20), (x + 8, y - 27)])
        # 下颌线（硬朗轮廓）
        pygame.draw.line(screen, (166, 148, 134), (x - 6, y - 20), (x + 6, y - 20), 1)
        # 灰褐背头（向后梳理、顶部留长、侧边剃短）
        pygame.draw.circle(screen, (132, 104, 76), (x, y - 31), 8)
        pygame.draw.polygon(screen, (110, 86, 62),
                            [(x - 9, y - 30), (x - 3, y - 38), (x + 3, y - 38), (x + 9, y - 30),
                             (x + 3, y - 34), (x - 3, y - 34)])
        pygame.draw.line(screen, (152, 122, 90), (x - 2, y - 37), (x + 5, y - 35), 2)       # 发丝高光
        # 铁灰狭长冷眼（狙击手的平直眼神，细长）
        pygame.draw.line(screen, (68, 74, 82), (x - 7, y - 26), (x - 2, y - 27), 2)
        pygame.draw.line(screen, (68, 74, 82), (x + 1, y - 27), (x + 6, y - 26), 2)
        pygame.draw.circle(screen, (52, 58, 66), (x + 4, y - 26), 1)                        # 左眼瞳（收紧）
        # 左眉弹片旧疤（保留角色印记）
        pygame.draw.line(screen, (226, 208, 196), (x - 7, y - 29), (x - 3, y - 30), 1)
        # ---- 重型栓动狙击步枪：抵肩瞄准姿态（枪口朝前上方，更长的枪身） ----
        pygame.draw.line(screen, (56, 50, 44), (x - 16, y - 14), (x + 20, y - 24), 5)       # 枪管
        pygame.draw.line(screen, (88, 76, 64), (x - 16, y - 14), (x - 4, y - 17), 3)        # 枪机高光
        pygame.draw.circle(screen, (120, 110, 96), (x - 18, y - 13), 4)                     # 瞄准镜
        pygame.draw.line(screen, (190, 180, 160), (x - 19, y - 15), (x - 17, y - 14), 1)    # 镜片反光
        pygame.draw.line(screen, (48, 44, 38), (x + 8, y - 23), (x + 16, y - 22), 3)        # 枪托
        pygame.draw.line(screen, (70, 62, 54), (x + 12, y - 23), (x + 16, y - 22), 1)       # 枪托木纹
        # 抵肩托枪手（扣在扳机护圈前）
        pygame.draw.circle(screen, (198, 180, 164), (x + 9, y - 20), 3)
        pygame.draw.circle(screen, (170, 152, 138), (x - 8, y - 12), 3)                     # 前手持枪
        # ---- 大招强化（战术再部署）：金色轮廓 + 双层脉冲光弧，更醒目 ----
        if self.sniper_ult > 0:
            pygame.draw.circle(screen, (255, 215, 90), (x, y - 27), 14, 1)
            pygame.draw.circle(screen, (255, 235, 160), (x, y - 27), 17 + (self.anim_t // 4) % 3, 1)
            pygame.draw.line(screen, (255, 225, 120), (x, y - 44), (x, y - 50), 2)          # 头顶金色光柱
        # 血条由主 draw() 统一绘制（这里不再自绘，避免出现双血条）

def draw_unit_icon(screen, unit, cx, cy, size):
    """把耕地者的完整 Q 版形象离屏渲染后缩略绘制到卡片/卡槽上。"""
    d = Defender(unit["uid"], 0, 0)          # 用数据区即时创建临时角色
    d.icon_mode = True                       # 图标模式：不画血条
    surf = pygame.Surface((96, 96), pygame.SRCALPHA)
    d.x, d.y = 48, 50                        # 画在临时画布中心
    d.draw(surf)
    img = pygame.transform.smoothscale(surf, size)
    screen.blit(img, (cx - size[0] // 2, cy - size[1] // 2))


class BoltFx:
    """莱昂纳多链式电弧：两点之间的蓝色闪电折线，闪烁数帧后消失。"""
    def __init__(self, x1, y1, x2, y2):
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2
        self.life = 8

    def update(self):
        self.life -= 1
        return self.life > 0

    def draw(self, screen):
        pts = []
        seg = 6
        for i in range(1, seg):
            t = i / seg
            mx = self.x1 + (self.x2 - self.x1) * t + random.uniform(-11, 11)
            my = self.y1 + (self.y2 - self.y1) * t + random.uniform(-8, 8)
            pts.append((mx, my))
        pts.append((self.x2, self.y2))
        pygame.draw.lines(screen, (110, 170, 255), False, [(self.x1, self.y1)] + pts, 3)
        pygame.draw.lines(screen, (225, 240, 255), False, [(self.x1, self.y1)] + pts, 1)


class HelioSealFx:
    """赫利俄恒光刻印：从棱镜射向目标的金色光束（带波纹），
       目标处金色菱形印记短暂爆发闪烁，数帧后消失。"""
    def __init__(self, x1, y1, x2, y2):
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2
        self.life = 14

    def update(self):
        self.life -= 1
        return self.life > 0

    def draw(self, screen):
        lf = self.life
        # 光束从棱镜射向目标，带轻微波纹
        n = 8
        pts = [(self.x1, self.y1)]
        for i in range(1, n):
            t = i / n
            mx = self.x1 + (self.x2 - self.x1) * t
            my = self.y1 + (self.y2 - self.y1) * t + math.sin(i * 1.4 + lf * 0.5) * 3
            pts.append((mx, my))
        pts.append((self.x2, self.y2))
        pygame.draw.lines(screen, (255, 200, 90), False, pts, 3)
        pygame.draw.lines(screen, (255, 245, 210), False, pts, 1)
        # 目标处金色菱形印记（外圈随帧扩张淡化 + 内芯闪烁）
        r = 5 + (14 - lf)
        pygame.draw.polygon(screen, (255, 210, 110),
                            [(self.x2, self.y2 - r - 6), (self.x2 + r, self.y2 - 6),
                             (self.x2, self.y2 + r - 6), (self.x2 - r, self.y2 - 6)], 2)
        pygame.draw.polygon(screen, (255, 245, 220),
                            [(self.x2, self.y2 - 5), (self.x2 + 4, self.y2 - 6),
                             (self.x2, self.y2 - 1), (self.x2 - 4, self.y2 - 6)])


class RogSlashFx:
    """罗格斩击特效：一片横扫刀光（覆盖 2×3 或整行范围）。
       渐变光带 + 中央亮刀光弧线，元素色随形态变化（物理灰白/火红/冰蓝/毒绿），数帧淡出。"""
    def __init__(self, x, y, w, h, color, life=10):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.color = color
        self.life = life

    def update(self):
        self.life -= 1
        return self.life > 0

    def draw(self, screen):
        lf = max(0, self.life)
        total = 10.0
        a = int(60 + 60 * (lf / total))          # 光带透明度随帧减弱
        c = self.color
        surf = pygame.Surface((int(self.w), int(self.h)), pygame.SRCALPHA)
        # 横向渐变光带：两段淡色铺满横扫范围
        pygame.draw.rect(surf, (c[0], c[1], c[2], min(255, a // 2)), surf.get_rect(), 0)
        # 中央亮刀光弧线（横扫的主刀光）
        midy = int(surf.get_height() * 0.5)
        hl = (min(255, c[0] + 110), min(255, c[1] + 110), min(255, c[2] + 110), min(255, a))
        pygame.draw.line(surf, hl, (0, midy), (int(surf.get_width()), midy), 3)
        # 上下两条残影刀光（更淡）
        pygame.draw.line(surf, (c[0], c[1], c[2], min(255, a // 2)),
                         (0, midy - 6), (int(surf.get_width()), midy - 6), 2)
        pygame.draw.line(surf, (c[0], c[1], c[2], min(255, a // 2)),
                         (0, midy + 6), (int(surf.get_width()), midy + 6), 2)
        screen.blit(surf, (int(self.x), int(self.y)))


class RogRowFx:
    """罗格三行裂斩专属特效：在自身行±1行覆盖区内爆开元素专属效果（不再用整道光带）。
       fire=多道火焰喷涌；poison=毒液滴落+底部毒雾弥漫；ice=地面刺出冰刺阵列。数帧淡出。"""
    def __init__(self, x, y, w, h, mode, life=14):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.mode = mode                 # fire / poison / ice
        self.life = life
        rnd = random.Random(id(self) & 0xffff)   # 固定布局，防闪烁
        self.seeds = []
        for _ in range(int(w // 42) + 2):
            self.seeds.append((rnd.uniform(self.x, self.x + self.w),
                               rnd.uniform(self.y, self.y + self.h),
                               rnd.uniform(0.5, 1.0), rnd.uniform(0, 6.28)))

    def update(self):
        self.life -= 1
        return self.life > 0

    def draw(self, screen):
        lf = max(0, self.life)
        total = 14.0
        t = 1 - lf / total                    # 生长进度 0→1
        a = min(1.0, lf / 4 + 0.3)            # 淡出系数
        if self.mode == "fire":
            # 多道火焰喷涌：外层橙红火舌 + 内层亮黄焰心，随帧起伏
            for (px, py, sc, ph) in self.seeds:
                hgt = CELL_H * 0.8 * sc * (0.5 + 0.5 * math.sin(self.life * 0.6 + ph))
                base = py + CELL_H * 0.25
                pygame.draw.polygon(screen, (230, 90, 45),
                                    [(px - 11, base), (px + 11, base), (px, base - hgt)])
                pygame.draw.polygon(screen, (255, 190, 70),
                                    [(px - 5, base - 2), (px + 5, base - 2), (px, base - hgt * 0.72)])
                pygame.draw.polygon(screen, (255, 235, 150),
                                    [(px - 2, base - 4), (px + 2, base - 4), (px, base - hgt * 0.4)])
        elif self.mode == "poison":
            # 毒液滴从区域上方滴落 + 毒雾椭圆（居中一格）
            for (px, py, sc, ph) in self.seeds:
                drop_y = self.y + CELL_H * (0.5 + 0.35 * (0.5 + 0.5 * math.sin(self.life * 0.5 + ph)))
                r = 3 + 2 * sc
                pygame.draw.circle(screen, (140, 200, 75), (int(px), int(drop_y)), int(r))
                pygame.draw.circle(screen, (190, 235, 120), (int(px - 2), int(drop_y - 2)), max(1, int(r * 0.5)))
            fog = pygame.Surface((int(self.w), int(CELL_H * 0.45)), pygame.SRCALPHA)
            pygame.draw.ellipse(fog, (135, 200, 75, int(70 * a)), fog.get_rect())
            screen.blit(fog, (int(self.x), int(self.y + CELL_H - CELL_H * 0.22)))
        elif self.mode == "ice":
            # 地面刺出冰刺阵列（随 t 从地面长出），带高光棱面
            ground = self.y + self.h * 0.8
            for (px, py, sc, ph) in self.seeds:
                hgt = CELL_H * 0.65 * sc * t + 2
                pygame.draw.polygon(screen, (165, 212, 245),
                                    [(px - 6, ground), (px + 6, ground), (px, ground - hgt)])
                pygame.draw.polygon(screen, (215, 240, 255),
                                    [(px - 2, ground - 2), (px, ground - hgt + 6), (px + 2, ground - 2)])
        elif self.mode == "physical":
            # 物理尖刺：灰色金属尖刺阵列从地面刺出（基础罗格普攻横扫）
            ground = self.y + self.h * 0.8
            for (px, py, sc, ph) in self.seeds:
                hgt = CELL_H * 0.6 * sc * t + 2
                pygame.draw.polygon(screen, (140, 142, 148),
                                    [(px - 6, ground), (px + 6, ground), (px, ground - hgt)])
                pygame.draw.polygon(screen, (200, 202, 208),
                                    [(px - 2, ground - 2), (px, ground - hgt + 6), (px + 2, ground - 2)])


class RogDragonFx:
    """罗格裂斩元素龙：一条对应元素的龙从罗格所在格沿自身行向场外飞过一整行。
       fire=火焰龙、ice=冰晶龙、poison=毒龙；身体为起伏长条 + 龙头 + 尾迹。"""
    def __init__(self, x0, y, row_w, mode, life=18):
        self.x = x0                     # 起点（罗格位置）
        self.y = y                      # 自身行中线
        self.row_w = row_w              # 整行飞行距离
        self.mode = mode                # fire / ice / poison
        self.life = life
        self.speed = row_w / life       # 每帧向前推进

    def update(self):
        self.x += self.speed
        self.life -= 1
        return self.life > 0

    def draw(self, screen):
        # 元素配色
        if self.mode == "fire":
            body, edge, wing = (255, 140, 60), (255, 210, 90), (230, 90, 45)
        elif self.mode == "ice":
            body, edge, wing = (170, 215, 255), (220, 240, 255), (120, 185, 240)
        else:  # poison
            body, edge, wing = (160, 215, 85), (205, 240, 130), (120, 190, 70)
        head_x = self.x
        tail_len = CELL_W * 6.0                      # 身体长度（2.5倍放大，更威猛）
        seg = 26
        pts = []
        for i in range(seg):
            px = head_x - tail_len * i / seg
            py = self.y + math.sin(self.life * 0.45 + i * 0.5) * 8   # 身体S形波动（加大起伏）
            pts.append((px, py))
        # 身体主条（粗）
        pygame.draw.lines(screen, body, False, pts, 12)
        # 身体外发光（更粗的暗色底，增强立体感）
        pygame.draw.lines(screen, wing, False, pts, 16)
        pygame.draw.lines(screen, body, False, pts, 12)
        # 鳞片高光点（沿身体亮点）
        for i in range(0, seg, 2):
            pygame.draw.circle(screen, edge, (int(pts[i][0]), int(pts[i][1]) - 6), 4)
        # 翅膀（身体两侧大三角，元素色）
        mid = seg // 2
        wx, wy = pts[mid]
        pygame.draw.polygon(screen, wing,
                            [(wx, wy), (wx - 28, wy - 38), (wx + 26, wy - 20)])
        pygame.draw.polygon(screen, wing,
                            [(wx, wy), (wx - 24, wy + 36), (wx + 24, wy + 18)])
        # 龙头（前方）：尖头三角 + 眼 + 龙角（加大）
        pygame.draw.polygon(screen, edge,
                            [(head_x + 22, self.y), (head_x - 10, self.y - 18), (head_x - 10, self.y + 18)])
        pygame.draw.circle(screen, (20, 20, 24), (int(head_x - 4), int(self.y - 4)), 4)
        # 龙角（头两侧向后）
        pygame.draw.polygon(screen, edge,
                            [(head_x - 4, self.y - 16), (head_x - 18, self.y - 26), (head_x - 8, self.y - 12)])
        pygame.draw.polygon(screen, edge,
                            [(head_x - 4, self.y + 16), (head_x - 18, self.y + 26), (head_x - 8, self.y + 12)])
        # 尾迹：尾部向后渐隐的大光点
        for i in range(1, 7):
            tx = head_x - tail_len - i * 14
            pygame.draw.circle(screen, body, (int(tx), int(self.y + math.sin(self.life * 0.45) * 6)), max(1, 7 - i))


class StormFx:
    """雷暴领域特效：3行×5格矩形雷电网格，蓝色电弧随机跳动数秒后消失。"""
    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.timer = 40

    def update(self):
        self.timer -= 1
        return self.timer > 0

    def draw(self, screen):
        t = max(self.timer, 0)
        alpha = int(60 + (t / 40) * 90)
        ov = pygame.Surface((int(self.w), int(self.h)), pygame.SRCALPHA)
        ov.fill((120, 160, 255, alpha // 2))             # 半透明雷电场底
        for _ in range(10):                              # 随机电弧跳动
            x0 = random.uniform(0, self.w)
            y0 = random.uniform(0, self.h)
            x1 = min(self.w, x0 + random.uniform(12, 70))
            pygame.draw.line(ov, (150, 190, 255, min(230, alpha + 90)), (x0, y0), (x1, y0 + random.uniform(-16, 16)), 2)
        pygame.draw.rect(ov, (130, 175, 255, min(200, alpha + 60)), ov.get_rect(), 2, border_radius=8)
        screen.blit(ov, (int(self.x), int(self.y)))


class FireZone:
    """伊格尼斯的燃烧瓶火区：覆盖自身格+前方1格（2格宽），持续燃烧4秒。"""
    def __init__(self, x, y, ignis):
        self.x, self.y = x, y
        self.w = CELL_W * 2                 # 火区宽度：2格
        self.life = ignis.fire_sec * FPS    # 持续秒数
        self.dot = ignis.fire_dot           # 火区持续伤害/秒
        self.burn = ignis.burn              # 灼烧伤害/秒
        self.burn_sec = ignis.burn_sec      # 灼烧持续秒数
        self.frame = 0
        self.attrs = ignis.atk_snapshot()   # 攻击方属性快照（火区结算用）

    def in_range(self, m):
        """火区判定：同行 ±0.7格高度，横向覆盖 自身格+前方1格。"""
        return ((m.giant or abs(m.y - self.y) < CELL_H * 0.7) and
                self.x - CELL_W * 0.5 <= m.x <= self.x + CELL_W * 1.5)

    def update(self, ctx):
        self.life -= 1
        if self.life <= 0:
            return False
        self.frame += 1
        # 每秒一次：火区持续伤害150 + 给敌人挂灼烧100/s（持续4秒）
        if self.frame % FPS == 0:
            for m in ctx["monsters"][:]:
                if self.in_range(m) and not getattr(m, "spawn_protect", False):
                    # 火区持续伤害：统一公式（攻击属性=伊格尼斯快照），持续伤害不暴击
                    snap = dict(self.attrs); snap["crit_rate"] = 0.0
                    snap.pop("true_dmg", 0)   # 持续伤害不附带攻击型真实伤害
                    dmg, _ = DamageSystem.calc(base_atk=self.dot, element="fire",
                                               defense=m.defense, resist=m.resist_of("fire"), **snap)
                    m.take_hit(dmg, "aoe")
                    ctx["scene"].fx.append(FloatingText(m.x, m.y - 26, f"-{dmg}", DAMAGE_COLOR_FIRE))
                    m.burn_dmg = self.burn
                    m.burn_timer = self.burn_sec * FPS
                    snap = dict(self.attrs); snap["crit_rate"] = 0.0
                    snap.pop("true_dmg", 0)
                    m.burn_attrs = snap
                    if m.hp <= 0:
                        m.die(ctx["scene"])
        return True

    def draw(self, screen):
        # 地面火焰：两层橙色 + 顶部火舌跳动
        pygame.draw.rect(screen, (60, 20, 10), (self.x - self.w // 2, self.y - 18, self.w, 26), border_radius=6)
        pygame.draw.rect(screen, (230, 110, 30), (self.x - self.w // 2 + 4, self.y - 16, self.w - 8, 22), border_radius=6)
        for i in range(3):
            fx = self.x - self.w // 2 + 18 + i * (self.w - 36) // 2 + random.randint(-6, 6)
            fh = 14 + random.randint(-4, 4)
            pygame.draw.polygon(screen, (255, 200, 60),
                                [(fx - 7, self.y - 14), (fx, self.y - 14 - fh), (fx + 7, self.y - 14)])


class IceNightFx:
    """白夜SP·永夜：自身行及相邻两行前方的大范围冰场，持续4秒。
    场内敌人陷入冻结（无法移动/攻击），每秒受600点冰元素伤害并挂寒冷；
    施法者在冰场持续期间无敌（由 Defender.invuln_timer 管理）。"""
    def __init__(self, x, y, baiye):
        self.x, self.y = x, y
        self.w = 6 * CELL_W                 # 覆盖宽度：自身格起前方约5格（与极乐冰宴同范围）
        self.h = 3 * CELL_H                 # 覆盖高度：3行（自身行±1行）
        self.life = 4 * FPS                 # 持续4秒
        self.dot = baiye.ult                # 每秒600冰伤
        self.frame = 0
        self.attrs = baiye.atk_snapshot()   # 攻击方属性快照（冰场结算用）

    def in_range(self, m):
        """永夜冰场判定：自身行±1行（3行宽），横向覆盖自身格+前方约5格。"""
        return ((m.giant or abs(m.y - self.y) < CELL_H * 1.5) and
                self.x - CELL_W * 0.5 <= m.x <= self.x + 5.5 * CELL_W)

    def update(self, ctx):
        self.life -= 1
        if self.life <= 0:
            return False
        self.frame += 1
        # 每秒一次：场内敌人保持冻结+寒冷，受600冰伤
        if self.frame % FPS == 0:
            for m in ctx["monsters"][:]:
                if self.in_range(m) and not getattr(m, "spawn_protect", False):
                    m.freeze_timer = max(m.freeze_timer, 4 * FPS)   # 冰场期间持续冻结
                    m.cold_timer = max(m.cold_timer, 5 * FPS)        # 同时获得寒冷
                    snap = dict(self.attrs); snap["crit_rate"] = 0.0
                    snap.pop("true_dmg", 0)   # 持续伤害不附带攻击型真实伤害
                    dmg, _ = DamageSystem.calc(base_atk=self.dot, element="ice",
                                               defense=m.defense, resist=m.resist_of("ice"), **snap)
                    m.take_hit(dmg, "aoe")
                    ctx["scene"].fx.append(FloatingText(m.x, m.y - 26, f"-{dmg}", DAMAGE_COLOR_ICE))
                    m.frost_dmg = 100
                    m.frost_timer = 4 * FPS
                    m.frost_attrs = dict(snap)
                    if m.hp <= 0:
                        m.die(ctx["scene"])
        return True

    def draw(self, screen):
        # 永夜冰场：淡蓝冰面 + 冰晶棱线 + 飘落寒晶（随时间流动，明显区别于火区）
        pygame.draw.rect(screen, (40, 80, 120), (self.x - self.w // 2, self.y - self.h // 2, self.w, self.h), border_radius=12)
        pygame.draw.rect(screen, (150, 215, 255), (self.x - self.w // 2 + 4, self.y - self.h // 2 + 4, self.w - 8, self.h - 8), 2, border_radius=12)
        t = pygame.time.get_ticks()
        for i in range(10):
            px = self.x - self.w // 2 + 18 + (t // 7 + i * 71) % (self.w - 36)
            py = self.y - self.h // 2 + 12 + (t // 11 + i * 97) % (self.h - 24)
            pygame.draw.circle(screen, (205, 240, 255), (int(px), int(py)), 2)


class Monster:
    """怪物：从右向左进攻，遇到单位停下啃咬，走到最左则基地失守。"""
    def __init__(self, uid, row):
        d = next(m for m in MONSTERS if m["uid"] == uid)
        self.uid = uid
        self.name = d["name"]
        self.maxhp = d["hp"]
        self.hp = self.maxhp
        self.speed = d["speed"]
        self.atk = d["atk"]
        self.color = d["color"]
        self.giant = d.get("giant", False)      # 巨型怪：身体横跨全部5行，任意行的单位都能打到它
        # 出生在最右列中心（巨型怪身体宽66，向左让出半身，右边缘贴出生点）
        self.x = (GRID_COLS - 1) * CELL_W + CELL_W // 2 - (33 if self.giant else 0)
        self.y = GRID_TOP + row * CELL_H + CELL_H // 2
        if self.giant:
            # 巨型怪固定在中心行，身体从网格顶延伸到网格底，覆盖全部5行
            self.y = GRID_TOP + (GRID_ROWS // 2) * CELL_H + CELL_H // 2
        self.row = row                          # 所在行（召唤/分散用）
        self.hp_mult = 1.0                      # 难度血量倍率（由战斗场景生成时设置）
        # ---- 护甲 / 特殊机制（新怪物体系）----
        self.armor = d.get("armor", 0)          # 护甲值（混凝土盾/气瓶/碎片）
        self.armor_max = self.armor
        self.armor_type = d.get("armor_type", None)   # shield/tank/scrap
        self.break_to = d.get("break_to", None)       # 破甲后转换的怪物uid
        self.boom = d.get("boom", 0)                  # 气瓶爆裂溅射伤害（打身前一格植物）
        self.pending_boom = False                     # 待处理的溅射标记
        self.hit_boost = d.get("hit_boost", False)    # 变异犬：受击短暂加速
        self.speed_break = d.get("speed_break", 0)    # 冲刺者：受击/破甲后移速
        self.hit_speed_timer = 0                      # 受击加速剩余帧数
        self.shatter = d.get("shatter", False)        # 夯骨巨汉：一击摧毁防御单位
        # ---- 伤害结算属性（受击方）----
        self.defense = d.get("defense", 0.0)        # 防御值（直接抵扣攻击）
        self.base_defense = self.defense            # 原始防御备份（罗格SP腐蚀减防用，腐蚀结束恢复）
        self.resist = d.get("resist", 0.0)          # 抗性%（统一值，或 dict{元素:百分比} 按元素细分）
        self.atk_iv = d.get("atk_iv", 1)              # 攻击间隔（帧，1=每帧攻击）
        self.atk_timer = self.atk_iv                # 初始先等一个攻击间隔，避免出场即攻击
        self.summon = d.get("summon", None)           # 血量过半召唤的怪物uid
        self.summon_num = d.get("summon_num", 2)
        self.summoned = False                         # 是否已召唤（仅一次）
        self.w = d.get("w", 30)                       # 绘制体型宽
        self.h = d.get("h", 40)                       # 绘制体型高
        self.action = 0.0
        self.burn_dmg = 0        # 灼烧伤害/秒（伊格尼斯燃烧瓶）
        self.burn_timer = 0      # 灼烧剩余帧数
        self.cold_timer = 0      # 寒冷剩余帧数（冰伤附加，持续5秒：移速/攻速-40%、物理/冰抗-20%）
        self.wet_timer = 0       # 潮湿剩余帧数（水伤附加，持续5秒）
        self.paralyze_timer = 0  # 麻痹剩余帧数（雷伤附加：0.4秒无法移动/攻击）
        self.freeze_timer = 0    # 冻结剩余帧数（白夜极乐冰宴，冻结期间无法移动/攻击）
        self.res_cut = 0.0       # 全元素抗性降低%（卡斯珀SP奔流浪涛附加，攻击方施加）
        self.res_cut_timer = 0   # 减抗剩余帧数
        self.kb_x = None          # 击退目标x（卡斯珀暗潮漩涡：缓慢向后推，None=不在击退中）
        self.kb_speed = 0.0       # 击退每帧位移（约0.9秒推完4格）
        self.frost_dmg = 0       # 冻伤伤害/秒（极乐冰宴附加）
        self.frost_timer = 0     # 冻伤剩余帧数
        self.hit_fx_cd = 0       # 啃咬伤害数字显示冷却（防止每帧刷屏）
        self.burn_attrs = {}     # 灼烧攻击方属性快照（伊格尼斯）
        self.frost_attrs = {}    # 冻伤攻击方属性快照（白夜）
        # ---- 腐蚀（毒元素，罗格SP腐毒形态）----
        self.poison_dmg = 0      # 腐蚀每层每秒毒伤（罗格SP：20/层）
        self.poison_stack = 0    # 腐蚀层数（最多3层）
        self.poison_timer = 0    # 腐蚀剩余帧数
        self.poison_attrs = {}   # 腐蚀毒伤攻击方属性快照
        self.dummy = d.get("dummy", False)   # 测试沙包（DPS试炼场）：不移动不攻击、死亡原地复活
        # 生成保护：刚生成在最右列（最后一格）时不被攻击，走到第二格才解除；
        # DPS试炼场的固定沙包例外（原地不动，不能有保护，否则无法输出）
        self.spawn_protect = not self.dummy
        self.dmg_received = 0                # 累计受到的总伤害（DPS统计，每帧由场景清零累计）
        # ---- 新怪物机制（第4关起）----
        self.stampede = d.get("stampede", False)      # 辐射蛮牛：攻击时践踏身后一格同排单位
        self.ranged = d.get("ranged", False)          # 远程怪：停在防线前远程输出，不近战啃咬
        self.r_atk_iv = d.get("r_atk_iv", 120)        # 远程攻击间隔（帧）
        self.r_atk_timer = self.r_atk_iv
        self.r_dmg = d.get("r_dmg", 10)               # 远程单次伤害
        self.r_dot = d.get("r_dot", 0)                # 腐蚀持续伤害/秒
        self.r_dot_len = d.get("r_dot_len", 0)        # 腐蚀持续帧数
        self.r_true = d.get("true_dmg", False)        # 酸液喷射者：远程伤害为真实伤害（无视防御）
        self.acid_target = None                       # 腐蚀目标（防御单位引用）
        self.acid_timer = 0                           # 腐蚀剩余帧数
        self.r_stop_x = d.get("r_stop_x", 6 * CELL_W + CELL_W // 2)  # 远程怪停下位置（第6列中心）
        self.jump_cd = d.get("jump_cd", 0)            # 迅猛龙：跳跃间隔（帧），0=不会跳
        self.jump_timer = self.jump_cd
        self.jump_dist = d.get("jump_dist", 150)      # 跳跃距离（像素，约1.5格）
        self.death_boom = d.get("death_boom", 0)      # 死亡溅射伤害（霜皮丧尸冰爆）
        self.death_boom_el = d.get("death_boom_element", "physical")
        self.death_summon = d.get("death_summon", None)   # 死亡召唤的怪物uid（废土尸王）
        self.death_summon_num = d.get("death_summon_num", 0)
        self.spd_mult = 1.0                           # 关卡规则移速倍率（沙尘暴/精英血脉）

    def update(self, ctx):
        # 测试沙包（DPS试炼场）：每5秒自动回满血——可被持续压血，但周期性重置，永远打不死
        if self.dummy:
            self._dummy_t = getattr(self, "_dummy_t", 0) + 1
            if self._dummy_t >= 5 * FPS:
                self._dummy_t = 0
                self.hp = self.maxhp
                self.armor = self.armor_max
        # 生成保护解除：走出第一格的最左边边界即解除（保护范围严格限定为最右列第一格）
        if self.spawn_protect and self.x < (GRID_COLS - 1) * CELL_W:
            self.spawn_protect = False
        # 生成保护期间：完全不被当作可攻击对象——清除一切已附加的伤害/状态（冻住、灼烧、腐蚀等），
        # 且下方所有持续伤害、状态计时一律不计（即使被范围技能误扫到也瞬间清零）
        if self.spawn_protect:
            self.burn_timer = self.frost_timer = self.poison_timer = 0
            self.freeze_timer = self.cold_timer = self.wet_timer = self.paralyze_timer = 0
            self.burn_dmg = self.frost_dmg = self.poison_dmg = 0
        # 夯骨巨汉：血量降到一半时踩踏大地，召唤尘窟窜童破土而出（仅一次）
        if self.summon and not self.summoned and self.hp < self.maxhp * 0.5:
            self.summoned = True
            for _ in range(self.summon_num):
                r = max(0, min(GRID_ROWS - 1, self.row + random.choice([-1, 1])))
                ch = Monster(self.summon, r)
                ch.x = self.x - 180      # 破土出现在巨汉前方（冲向前排）
                ch.hp_mult = self.hp_mult   # 召唤的窜童继承难度倍率
                if self.hp_mult != 1.0:
                    ch.maxhp = int(ch.maxhp * self.hp_mult)
                    ch.hp = ch.maxhp
                    ch.armor = int(ch.armor * self.hp_mult)
                    ch.armor_max = ch.armor
                ctx["scene"].monsters.append(ch)
                ctx["scene"].fx.append(FloatingText(ch.x, ch.y - 26, "破土而出！", (200, 160, 120), 14))
        # 锈蚀气瓶兵：气瓶爆裂后对身前一格植物溅射伤害
        if self.pending_boom:
            self.pending_boom = False
            for d in ctx["defenders"]:
                if getattr(d, "untargetable", False):
                    continue
                if abs(d.y - self.y) < 45 and 0 < self.x - d.x < 100:
                    dmg = d.take_damage(self.boom)
                    ctx["scene"].fx.append(FloatingText(d.x, d.y - 26, f"-{int(dmg)}", DAMAGE_COLOR_PHYS, 14))
        # 灼烧效果（燃烧瓶）：每秒结算一次，走统一伤害公式（火元素，不暴击）
        if self.burn_timer > 0:
            self.burn_timer -= 1
            if self.burn_timer % FPS == 0:
                snap = dict(self.burn_attrs); snap.pop("true_dmg", 0)
                dmg, _ = DamageSystem.calc(base_atk=self.burn_dmg, element="fire",
                                           defense=self.defense, resist=self.resist_of("fire"),
                                           **snap)
                self.take_hit(dmg, "aoe")
                ctx["scene"].fx.append(FloatingText(self.x, self.y - 26, f"-{int(dmg)}", DAMAGE_COLOR_FIRE))
        # 冻伤效果（极乐冰宴）：每秒结算一次，走统一伤害公式（冰元素，不暴击）
        if self.frost_timer > 0:
            self.frost_timer -= 1
            if self.frost_timer % FPS == 0:
                snap = dict(self.frost_attrs); snap.pop("true_dmg", 0)
                dmg, _ = DamageSystem.calc(base_atk=self.frost_dmg, element="ice",
                                           defense=self.defense, resist=self.resist_of("ice"),
                                           **snap)
                self.take_hit(dmg, "aoe")
                ctx["scene"].fx.append(FloatingText(self.x, self.y - 26, f"-{int(dmg)}", DAMAGE_COLOR_ICE))
        # 腐蚀（毒元素，罗格SP腐毒形态）：每秒结算一层毒伤，同时维持减防18%/层；结束恢复原防御
        if self.poison_timer > 0:
            self.poison_timer -= 1
            if self.poison_timer % FPS == 0:
                snap = dict(self.poison_attrs); snap.pop("true_dmg", 0)
                dmg, _ = DamageSystem.calc(base_atk=self.poison_dmg * self.poison_stack, element="poison",
                                           defense=self.defense, resist=self.resist_of("poison"),
                                           **snap)
                self.take_hit(dmg, "aoe")
                ctx["scene"].fx.append(FloatingText(self.x, self.y - 26, f"-{int(dmg)}", DAMAGE_COLOR_POISON))
            if self.poison_timer <= 0:
                self.defense = self.base_defense     # 腐蚀结束，恢复原始防御
        # 寒冷 / 潮湿计时（元素状态）
        if self.cold_timer > 0:
            self.cold_timer -= 1
        if self.wet_timer > 0:
            self.wet_timer -= 1
        # 全元素减抗计时（卡斯珀SP奔流浪涛附加）
        if getattr(self, "res_cut_timer", 0) > 0:
            self.res_cut_timer -= 1
            if self.res_cut_timer <= 0:
                self.res_cut = 0.0
        # 啃咬伤害数字冷却递减
        if self.hit_fx_cd > 0:
            self.hit_fx_cd -= 1
        # 变异犬受击加速剩余帧递减
        if self.hit_speed_timer > 0:
            self.hit_speed_timer -= 1
        # 冻结（极乐冰宴）：3秒内无法移动、无法攻击
        if self.freeze_timer > 0:
            self.freeze_timer -= 1
            return
        # 麻痹（雷伤）：0.4秒内无法移动、无法攻击（比冻结短，无冻伤）
        if self.paralyze_timer > 0:
            self.paralyze_timer -= 1
            return
        # 腐蚀诅咒（污染术士/酸液喷射者）：对目标防御单位持续掉血
        if self.acid_timer > 0:
            self.acid_timer -= 1
            t = self.acid_target
            if t is not None and t not in ctx["defenders"]:
                self.acid_target = None
                t = None
            if t is not None and self.acid_timer % FPS == 0:
                if self.r_true:
                    t.hp -= self.r_dot
                    ctx["scene"].fx.append(FloatingText(t.x, t.y - 26, f"-{self.r_dot}", (120, 230, 110), 12))
                else:
                    dmg2 = t.take_damage(self.r_dot)
                    ctx["scene"].fx.append(FloatingText(t.x, t.y - 26, f"-{int(dmg2)}", (120, 230, 110), 12))
                if t.hp <= 0 and t in ctx["defenders"]:
                    ctx["defenders"].remove(t)
        # 测试沙包（DPS试炼场）：以上状态与持续伤害照常结算，之后不移动、不攻击、不吃击退
        if self.dummy:
            return
        # 当前实际移速（寒冷-40%；变异犬受击时短暂爆发加速；关卡规则倍率）
        spd = self.speed * self.spd_mult * (0.6 if self.cold_timer > 0 else 1.0)
        if self.hit_speed_timer > 0:
            spd *= 1.4
        # 远程怪（污染术士/酸液喷射者）：被挡路或到达射程位置时停下远程输出，不近战啃咬
        if self.ranged:
            near_unit = False
            for d in ctx["defenders"]:
                if getattr(d, "untargetable", False):
                    continue
                if abs(d.y - self.y) < 45 and 0 < self.x - d.x < 60:
                    near_unit = True
                    break
            if (near_unit or self.x <= self.r_stop_x) and ctx["defenders"]:
                self.r_atk_timer -= 1
                if self.r_atk_timer <= 0:
                    self._ranged_attack(ctx)
                    self.r_atk_timer = self.r_atk_iv * (1.4 if self.cold_timer > 0 else 1.0)
            else:
                self.x -= spd
            if self.x < 20:
                ctx["scene"].game_over = True
            return
        # 击退状态（卡斯珀暗潮漩涡）：缓慢向后推，期间不前进/不攻击
        if self.kb_x is not None:
            if self.x + self.kb_speed >= self.kb_x:
                self.x = self.kb_x
                self.kb_x = None
            else:
                self.x += self.kb_speed
            return
        # 嘲讽：若场上有嘲讽中的布洛克（自身行或相邻行），强制向它靠近并攻击它
        taunter = None
        for d in ctx["defenders"]:
            # 巨型怪横跨全部5行：任意行的嘲讽单位都能吸引它
            if getattr(d, "taunt_timer", 0) > 0 and (self.giant or abs(d.y - self.y) < CELL_H + 12):
                taunter = d
                break
        if taunter is not None:
            # 嘲讽（布洛克·铁壁嘲讽）：把布洛克前方（尚未越过防线）、位于自身行+相邻两行的怪物
            # 在1秒内平滑移动到布洛克所在行（不改变移速/攻速）。布洛克后方已越过的怪不动。
            if self.x > taunter.x and abs(self.y - taunter.y) < CELL_H + 12:
                dy = taunter.y - self.y
                # 1秒内线性移动到布洛克行：固定步长（初始差/FPS），避免每帧重算剩余距离导致渐近永远到不了
                if getattr(self, "_taunt_target", None) != taunter.y:
                    self._taunt_dy = dy / FPS
                    self._taunt_target = taunter.y
                step = self._taunt_dy
                if abs(dy) > abs(step) + 1:
                    self.y += step
                    self.row = round((self.y - GRID_TOP) / CELL_H)
                    return
                else:
                    # 到位：吸附到布洛克行，复位步长，随后走下方 blocked 正常前进/啃咬
                    self.y = taunter.y
                    self.row = round((self.y - GRID_TOP) / CELL_H)
                    self._taunt_dy = None
                    self._taunt_target = None
            # 不 return、不主动攻击：继续走下方 blocked 啃咬逻辑（每秒一次），保持原移速
        # 找挡路的单位，优先最近的一个啃咬（巨型怪身体覆盖全部行，任意行单位都挡路）
        blocked = None
        for d in ctx["defenders"]:
            if getattr(d, "untargetable", False):
                continue       # 火元素无生命值，怪物不把它当目标
            if self.giant:
                if self.x - 66 <= d.x <= self.x + 55:   # 巨型怪身体范围内或其左前方的单位
                    blocked = d
                    break
            elif abs(d.y - self.y) < 45 and 0 < self.x - d.x < 55:
                blocked = d
                break
        if blocked:
            self.atk_timer -= 1
            if self.atk_timer <= 0:
                # 攻速修正：寒冷-40%（冷却变长）、灼烧+10%（冷却变短）
                self.atk_timer = self.atk_iv * (1.4 if self.cold_timer > 0 else 1.0) \
                                * (0.9 if self.burn_timer > 0 else 1.0)
                if self.shatter:
                    # 夯骨巨汉：钢筋一击直接摧毁防御单位
                    blocked.hp = 0
                    self._show_hit_fx(ctx, blocked.x, blocked.y, 999)
                else:
                    dmg, _ = DamageSystem.calc(
                        base_atk=self.atk, element="physical",
                        defense=getattr(blocked, "defense", 0.0),
                        resist=getattr(blocked, "resist", 0.0),
                        crit_rate=0.0, use_floor=False)
                    dmg = blocked.take_damage(dmg)
                    self._show_hit_fx(ctx, blocked.x, blocked.y, dmg)
                if blocked.hp <= 0 and blocked in ctx["defenders"]:
                    ctx["defenders"].remove(blocked)
                # 辐射蛮牛践踏：同时对挡路单位身后（防线方向）一格的同排单位造成伤害
                if self.stampede:
                    for d2 in list(ctx["defenders"]):
                        if getattr(d2, "untargetable", False):
                            continue
                        if abs(d2.y - self.y) < 45 and 0 < blocked.x - d2.x < 130:
                            dmg2, _ = DamageSystem.calc(
                                base_atk=self.atk, element="physical",
                                defense=getattr(d2, "defense", 0.0),
                                resist=getattr(d2, "resist", 0.0),
                                crit_rate=0.0, use_floor=False)
                            dmg2 = d2.take_damage(dmg2)
                            self._show_hit_fx(ctx, d2.x, d2.y, dmg2)
                            if d2.hp <= 0 and d2 in ctx["defenders"]:
                                ctx["defenders"].remove(d2)
        else:
            self.x -= spd
        # 裂爪迅猛龙：每5秒纵身一跃，无视挡路单位直接跳过防线（冻结/麻痹/击退时已提前返回）
        if self.jump_cd > 0 and self.x > 120:
            self.jump_timer -= 1
            if self.jump_timer <= 0:
                self.x -= self.jump_dist
                self.jump_timer = self.jump_cd
                ctx["scene"].fx.append(FloatingText(self.x, self.y - 30, "跳跃突袭！", (210, 210, 220), 12))
        # 走到最左：基地失守
        if self.x < 20:
            ctx["scene"].game_over = True
            if getattr(ctx["scene"], "endless", False):
                # 无尽模式一局失败：清除存档，下次进入将从第1关重新开始
                ctx["scene"].game.clear_endless_snapshot()

    def resist_of(self, element):
        """按元素取抗性：支持统一抗性（float）或按元素细分（dict）；
           寒冷状态下物理/冰抗性额外降低20%（允许降到负值=增伤）；
           卡斯珀SP全元素减抗（res_cut）同样直接扣除（可降到负值）。"""
        r = (self.resist.get(element, 0.0) if isinstance(self.resist, dict) else self.resist)
        if self.cold_timer > 0 and element in ("physical", "ice"):
            r = r - 0.2
        if getattr(self, "res_cut", 0.0) > 0:
            r = r - self.res_cut
        return r

    def take_hit(self, dmg, kind="bullet"):
        """统一受伤入口：按怪物护甲机制分配伤害。
        入口处先累计本次受到的伤害（dmg_received），供 DPS 试炼场统计总伤害。
        kind: bullet(直线单体攻击) / pierce(贯穿弹) / aoe(范围、持续伤害)
        - 混凝土盾手：盾只挡正面直线攻击；贯穿/范围攻击直接打本体
        - 锈蚀气瓶兵：护甲全方向防御，先打气瓶，打爆溅射+转换
        - 残骸冲刺者：碎片护甲先被打，受击即降速，破甲后转换
        - 变异犬：受击短暂爆发加速
        返回实际扣除的总伤害。"""
        # 生成保护：第一格（最右列）的怪物完全不被当作可攻击对象——不受伤、不累计DPS伤害
        if getattr(self, "spawn_protect", False):
            return 0
        self.dmg_received += dmg   # DPS统计：累计本帧受到的伤害（含护甲吸收的部分）
        # 爆炸伤害：无视一切防具/护甲防御（气瓶/盾/碎片护甲直接跳过）
        if kind == "explosive":
            self.hp -= dmg
            return dmg
        # 变异犬：受击短暂爆发加速冲刺
        if self.hit_boost:
            self.hit_speed_timer = 20
        # 残骸冲刺者：一旦受到伤害，碎片护甲脱落、移速骤降
        if self.armor_type == "scrap" and self.armor > 0:
            self.speed = self.speed_break
        # 混凝土盾手：盾只挡正面直线攻击（侧面/斜向=贯穿/范围直接打本体）
        if self.armor_type == "shield" and self.armor > 0 and kind == "bullet":
            self.armor -= dmg
            if self.armor <= 0:
                self.break_armor()
            return dmg
        # 锈蚀气瓶兵：护甲全方向防御，先打气瓶
        if self.armor_type == "tank" and self.armor > 0:
            self.armor -= dmg
            if self.armor <= 0:
                self.break_armor()      # 气瓶打爆：溅射 + 变拾荒者
            return dmg
        # 残骸冲刺者碎片护甲：所有伤害先打护甲
        if self.armor_type == "scrap" and self.armor > 0:
            self.armor -= dmg
            if self.armor <= 0:
                self.break_armor()
            return dmg
        # 普通本体受伤
        self.hp -= dmg
        return dmg

    def break_armor(self):
        """护甲/气瓶破碎：触发特殊效果，并按 break_to 转换为对应普通怪物（如拾荒者）。"""
        base = next(m for m in MONSTERS if m["uid"] == self.break_to)
        self.armor = 0
        self.armor_type = None
        self.maxhp = base["hp"]
        if self.hp > self.maxhp:
            self.hp = self.maxhp
        self.speed = base["speed"]
        self.atk = base["atk"]
        self.color = base["color"]
        self.name = base["name"]
        self.uid = base["uid"]
        self.w = base.get("w", 30)
        self.h = base.get("h", 40)
        if self.boom:
            self.pending_boom = True   # 气瓶爆裂：下一帧溅射身前一格植物

    def apply_cold(self, frames):
        """附加寒冷状态（刷新持续时间）：移速/攻速-40%、物理/冰抗-20%。"""
        self.cold_timer = max(self.cold_timer, frames)

    def die(self, scene):
        """怪物死亡：冻结状态下被击败→碎成冰渣；灼烧状态下→化为灰烬；
           两者都无法触发亡语（亡语系统为后续预留，当前怪物均无亡语）。
           测试沙包（dummy）例外：不死亡，原地重置复活（伤害已计入DPS统计）。"""
        if self.dummy:
            self.hp = self.maxhp
            self.armor = self.armor_max
            self.burn_timer = self.frost_timer = self.freeze_timer = 0
            self.cold_timer = self.wet_timer = self.paralyze_timer = 0
            self.kb_x = None
            scene.fx.append(FloatingText(self.x, self.y - 30, "沙包重置", (210, 190, 140), 12))
            return
        if self.freeze_timer > 0:
            scene.fx.append(ParticleFx(self.x, self.y, (185, 225, 250), 12))
        elif self.burn_timer > 0:
            scene.fx.append(ParticleFx(self.x, self.y, (95, 95, 100), 12))
        # 亡语规则：冻结/灼烧状态下被击败 → 碎成冰渣/化为灰烬，无法触发任何死亡机制
        if self.freeze_timer <= 0 and self.burn_timer <= 0:
            # 霜皮丧尸：冰甲爆裂，对周围（同排±120px）防御单位造成冰霜溅射
            if self.death_boom:
                for d in list(scene.defenders):
                    if getattr(d, "untargetable", False):
                        continue
                    if abs(d.y - self.y) < 45 and abs(d.x - self.x) < 120:
                        dmg = d.take_damage(self.death_boom)
                        scene.fx.append(FloatingText(d.x, d.y - 26, f"-{int(dmg)}", DAMAGE_COLOR_ICE, 12))
                        if d.hp <= 0 and d in scene.defenders:
                            scene.defenders.remove(d)
            # 废土尸王：尸气爆发，召唤拾荒者破土而出
            if self.death_summon:
                for _ in range(self.death_summon_num):
                    r = random.randint(0, GRID_ROWS - 1)
                    s = Monster(self.death_summon, r)
                    s.x = max(280, self.x - 60)
                    s.hp_mult = self.hp_mult
                    if self.hp_mult != 1.0:
                        s.maxhp = int(s.maxhp * self.hp_mult)
                        s.hp = s.maxhp
                        s.armor = int(s.armor * self.hp_mult)
                        s.armor_max = s.armor
                    scene.monsters.append(s)
                    scene.fx.append(FloatingText(s.x, s.y - 26, "尸气滋生！", (150, 120, 170), 12))
        if self in scene.monsters:
            scene.monsters.remove(self)

    def _ranged_attack(self, ctx):
        """远程攻击（污染术士/酸液喷射者）：随机选择一名防御单位施放诅咒/酸液，
           立即结算一次伤害（酸液为无视防御的真实伤害），并附加持续腐蚀。"""
        targets = [d for d in ctx["defenders"] if not getattr(d, "untargetable", False)]
        if not targets:
            return
        t = random.choice(targets)
        ctx["scene"].fx.append(FloatingText(t.x, t.y - 34, ("腐蚀诅咒" if not self.r_true else "酸液喷吐"), (150, 225, 130), 12))
        if self.r_true:
            # 真实伤害：数值是多少就是多少，无视防御/减伤
            t.hp -= self.r_dmg
            ctx["scene"].fx.append(FloatingText(t.x, t.y - 22, f"-{self.r_dmg}", DAMAGE_COLOR_PHYS, 12))
        else:
            dmg, _ = DamageSystem.calc(
                base_atk=self.r_dmg, element="physical",
                defense=getattr(t, "defense", 0.0),
                resist=getattr(t, "resist", 0.0),
                crit_rate=0.0, use_floor=False)
            dmg = t.take_damage(dmg)
            ctx["scene"].fx.append(FloatingText(t.x, t.y - 22, f"-{int(dmg)}", DAMAGE_COLOR_PHYS, 12))
        if t.hp <= 0 and t in ctx["defenders"]:
            ctx["defenders"].remove(t)
        if self.r_dot > 0:
            self.acid_target = t
            self.acid_timer = self.r_dot_len

    def _show_hit_fx(self, ctx, x, y, dmg):
        """怪物攻击我方单位时显示伤害数字（带冷却防刷屏；护盾全挡显示“格挡”）。"""
        if self.hit_fx_cd > 0:
            return
        if dmg <= 0:
            ctx["scene"].fx.append(FloatingText(x, y - 26, "格挡", (120, 170, 255), 12))
        else:
            d = max(1, int(round(dmg)))
            ctx["scene"].fx.append(FloatingText(x, y - 26, f"-{d}", DAMAGE_COLOR_PHYS, 12))
        self.hit_fx_cd = 10

    def draw(self, screen, mini=False):
        """mini=True：面板小图标模式（不画血条/护甲/冻结框，仅画身体）。"""
        # 生成保护期半透明绘制：整只怪先画到临时画布，再按约55%透明度混合到屏幕，露出网格
        if self.spawn_protect and not mini and not getattr(self, "_proto_render", False):
            self._proto_render = True
            surf = pygame.Surface((CELL_W * 2, CELL_H * 6), pygame.SRCALPHA)
            old = (self.x, self.y)
            try:
                self.x, self.y = CELL_W, CELL_H * 3      # 在临时画布内以中心坐标绘制本体
                self.draw(surf)                           # 递归：此时跳过保护分支，正常绘制
            finally:
                self.x, self.y = old
            self._proto_render = False
            surf.set_alpha(150)
            screen.blit(surf, (self.x - CELL_W, self.y - CELL_H * 3))
            return
        # 巨型怪（末日终结者）：身体横跨全部5行，单独绘制
        if self.giant:
            if mini:
                self._draw_giant_mini(screen)
            else:
                self._draw_giant(screen)
            return
        # 冰元素状态（寒冷/冻结/冻伤）时：身体整体偏蓝 + 蓝色小光环
        body = self.color
        if self.cold_timer > 0 or self.freeze_timer > 0 or self.frost_timer > 0:
            body = (min(body[0] + 50, 255), max(body[1] - 25, 30), min(body[2] + 95, 255))
            pygame.draw.circle(screen, (120, 190, 255), (self.x + 15, self.y - 10), 13, 1)
        # 按怪物类型绘制不同外形（护甲怪也一眼可辨）
        if self.uid == "m_hulk":
            self._draw_hulk(screen, body)
        elif self.uid == "m_shield":
            self._draw_shield(screen, body)
        elif self.uid == "m_tank":
            self._draw_tank(screen, body)
        elif self.uid == "m_sprint":
            self._draw_sprint(screen, body)
        elif self.uid == "m_child":
            self._draw_child(screen, body)
        elif self.uid == "m_dog":
            self._draw_dog(screen, body)
        elif self.uid == "m_dummy":
            self._draw_dummy(screen, body)
        elif self.uid == "m_wolf":
            self._draw_wolf(screen, body)
        elif self.uid == "m_brute":
            self._draw_brute(screen, body)
        elif self.uid == "m_hexer":
            self._draw_hexer(screen, body)
        elif self.uid == "m_spitter":
            self._draw_spitter(screen, body)
        elif self.uid == "m_raptor":
            self._draw_raptor(screen, body)
        elif self.uid == "m_frost":
            self._draw_frost(screen, body)
        elif self.uid == "m_king":
            self._draw_king(screen, body)
        elif self.uid == "m_colossus":
            self._draw_colossus(screen, body)
        elif self.uid == "m_queen":
            self._draw_queen(screen, body)
        elif self.uid == "m_tyrant":
            self._draw_tyrant(screen, body)
        elif self.uid == "m_leviathan":
            self._draw_leviathan(screen, body)
        else:
            self._draw_base(screen, body)
        if not mini:
            # 血量条 + 血量数字（头顶显示 当前/上限）
            rate = self.hp / self.maxhp
            pygame.draw.rect(screen, (70, 70, 70), (self.x, self.y - 28, self.w, 3))
            pygame.draw.rect(screen, (255, 60, 60), (self.x, self.y - 28, self.w * max(rate, 0), 3))
            if self.dummy:
                # 沙包血量太大：显示千分位简写（如 152K），避免数字溢出格子
                key = f"{int(self.hp / 1000)}K"
            else:
                key = f"{int(self.hp)}/{self.maxhp}"
            # 血条文本缓存：血量文本不变时不重复 render（怪多时的关键优化）
            if getattr(self, "_hp_key", None) != key:
                self._hp_key = key
                self._hp_img = make_font(12).render(key, True, COLOR_TEXT)
            screen.blit(self._hp_img, (self.x + self.w // 2 - self._hp_img.get_width() // 2, self.y - 40))
            # 护甲条（混凝土盾/气瓶/碎片）：黄色条在血条上方
            if self.armor > 0 and self.armor_type:
                ar = self.armor / self.armor_max
                pygame.draw.rect(screen, (70, 70, 80), (self.x, self.y - 36, self.w, 3))
                pygame.draw.rect(screen, (235, 205, 120), (self.x, self.y - 36, self.w * max(ar, 0), 3))
            # 冻结状态：蓝色冰框把怪物封冻住（像被冻在冰块里）
            if self.freeze_timer > 0:
                if getattr(self, "_ice_surf", None) is None:
                    ice = pygame.Surface((self.w + 8, self.h + 10), pygame.SRCALPHA)
                    ice.fill((160, 220, 255, 105))
                    pygame.draw.rect(ice, (215, 248, 255, 235), ice.get_rect(), 2, border_radius=5)
                    pygame.draw.polygon(ice, (225, 250, 255, 230),
                                        [(7, 6), ((self.w + 8) // 2, 0), (self.w + 1, 6)])   # 顶部冰晶尖角
                    self._ice_surf = ice
                screen.blit(self._ice_surf, (self.x - 4, self.y - 25))
            # 潮湿状态：蓝色小水滴漂浮在头顶
            if self.wet_timer > 0:
                pygame.draw.circle(screen, (90, 180, 255), (self.x + self.w // 2 - 8, self.y - 36), 4)
                pygame.draw.circle(screen, (140, 210, 255), (self.x + self.w // 2 + 6, self.y - 40), 3)
            # 麻痹状态：黄色闪电小图标（雷元素麻痹）
            if self.paralyze_timer > 0:
                pygame.draw.circle(screen, (255, 220, 90), (self.x + self.w // 2, self.y - 44), 6, 2)
                pygame.draw.line(screen, (255, 235, 120), (self.x + self.w // 2 - 2, self.y - 47),
                                 (self.x + self.w // 2 + 3, self.y - 41), 2)

    def _draw_dummy(self, screen, body):
        """测试沙包：黄褐大麻袋（扎口 + 补丁 + 靶心标记），DPS试炼场专用。"""
        x, y = self.x, self.y
        w, h = self.w, self.h
        # 麻袋主体（圆鼓鼓）
        pygame.draw.ellipse(screen, body, (x - w // 2, y - h // 2, w, h))
        pygame.draw.ellipse(screen, (196, 164, 110), (x - w // 2 + 4, y - h // 2 + 6, w - 8, h - 14))
        # 顶部扎口 + 系绳
        pygame.draw.line(screen, (140, 112, 72), (x - w // 2 + 6, y - h // 2 + 2), (x + w // 2 - 6, y - h // 2 + 2), 3)
        pygame.draw.line(screen, (120, 96, 60), (x, y - h // 2 + 1), (x, y - h // 2 - 4), 3)
        # 十字补丁（两处）
        pygame.draw.line(screen, (120, 96, 62), (x - w // 2 + 10, y - 2), (x - w // 2 + 22, y + 8), 2)
        pygame.draw.line(screen, (120, 96, 62), (x - w // 2 + 18, y - 2), (x - w // 2 + 10, y + 8), 2)
        # 靶心标记（中间圆圈 + 十字，像射击靶）
        pygame.draw.circle(screen, (120, 90, 56), (x + w // 2 - 10, y - h // 2 + 12), 5, 2)
        pygame.draw.line(screen, (120, 90, 56), (x + w // 2 - 15, y - h // 2 + 12), (x + w // 2 - 5, y - h // 2 + 12), 1)
        pygame.draw.line(screen, (120, 90, 56), (x + w // 2 - 10, y - h // 2 + 7), (x + w // 2 - 10, y - h // 2 + 17), 1)

    def _draw_base(self, screen, body):
        """废土拾荒者：破烂衣服的普通怪物。"""
        pygame.draw.rect(screen, body, (self.x, self.y - 20, self.w, self.h), border_radius=5)
        pygame.draw.circle(screen, (200, 60, 60), (self.x + self.w - 6, self.y - 6), 3)   # 眼睛
        pygame.draw.line(screen, (150, 130, 110), (self.x + self.w, self.y + 2),
                         (self.x + self.w + 6, self.y - 4), 2)                            # 手里断裂金属片

    def _draw_child(self, screen, body):
        """尘窟窜童：瘦小迅捷的变异孩童。"""
        pygame.draw.rect(screen, body, (self.x, self.y - 14, self.w, self.h - 2), border_radius=5)
        pygame.draw.circle(screen, (235, 225, 205), (self.x + self.w // 2, self.y - 18), 6)  # 头
        pygame.draw.circle(screen, (180, 60, 50), (self.x + self.w - 5, self.y - 6), 2)     # 眼睛

    def _draw_dog(self, screen, body):
        """变异犬：体型极小、皮肤泛红的小型变异禽类。"""
        pygame.draw.ellipse(screen, body, (self.x, self.y - 10, self.w, self.h))
        pygame.draw.circle(screen, (255, 90, 60), (self.x + self.w - 2, self.y - 8), 2)     # 红眼

    def _draw_shield(self, screen, body):
        """混凝土盾手：铁丝把混凝土墙块捆在身前当盾牌。"""
        pygame.draw.rect(screen, body, (self.x, self.y - 20, self.w, self.h), border_radius=5)
        pygame.draw.rect(screen, (150, 150, 155), (self.x - 14, self.y - 22, 14, self.h + 6), border_radius=2)  # 前方混凝土块
        pygame.draw.line(screen, (110, 105, 100), (self.x - 14, self.y - 18), (self.x, self.y - 18), 1)          # 铁丝
        pygame.draw.line(screen, (110, 105, 100), (self.x - 14, self.y + 12), (self.x, self.y + 12), 1)
        pygame.draw.circle(screen, (200, 60, 60), (self.x + self.w - 6, self.y - 6), 3)

    def _draw_tank(self, screen, body):
        """锈蚀气瓶兵：胸口绑着厚重锈蚀高压气瓶。"""
        pygame.draw.rect(screen, body, (self.x, self.y - 20, self.w, self.h), border_radius=5)
        pygame.draw.rect(screen, (168, 175, 182), (self.x + 6, self.y - 18, 16, self.h - 8), border_radius=4)   # 银色气瓶
        pygame.draw.line(screen, (120, 90, 60), (self.x + 8, self.y - 16), (self.x + 10, self.y + 12), 1)       # 锈蚀纹
        pygame.draw.line(screen, (120, 90, 60), (self.x + 14, self.y - 16), (self.x + 16, self.y + 12), 1)
        pygame.draw.circle(screen, (200, 60, 60), (self.x + self.w - 6, self.y - 6), 3)

    def _draw_hulk(self, screen, body):
        """夯骨巨汉：两米高的畸形巨人，拖着报废建筑钢筋。"""
        pygame.draw.rect(screen, body, (self.x, self.y - 28, self.w, self.h), border_radius=8)
        pygame.draw.circle(screen, (58, 54, 62), (self.x + self.w // 2, self.y - 34), 10)   # 头
        pygame.draw.circle(screen, (255, 80, 50), (self.x + self.w // 2 + 4, self.y - 34), 3)
        pygame.draw.line(screen, (130, 128, 125), (self.x + self.w + 2, self.y - 22),
                         (self.x + self.w + 22, self.y + 18), 5)                            # 拖着的钢筋
        pygame.draw.circle(screen, (90, 88, 85), (self.x + self.w + 21, self.y + 18), 3)

    def _draw_sprint(self, screen, body):
        """残骸冲刺者：轻量化金属碎片与轮胎皮防护。"""
        pygame.draw.rect(screen, body, (self.x, self.y - 20, self.w, self.h), border_radius=5)
        pygame.draw.circle(screen, (70, 66, 60), (self.x - 8, self.y + 4), 7, 2)             # 轮胎圈
        pygame.draw.circle(screen, (70, 66, 60), (self.x + self.w + 4, self.y + 4), 6, 2)
        pygame.draw.line(screen, (180, 180, 185), (self.x + 2, self.y - 16), (self.x + self.w - 2, self.y - 16), 2)  # 金属片
        pygame.draw.circle(screen, (200, 60, 60), (self.x + self.w - 6, self.y - 6), 3)

    def _draw_wolf(self, screen, body):
        """铁脊豺狼：灰黑色精英狼形，尖耳 + 狭长吻部 + 翘尾，眼神凶狠。"""
        x, y = self.x, self.y
        # 低伏身体
        pygame.draw.ellipse(screen, body, (x - 4, y - 12, self.w + 10, self.h - 14))
        # 头部 + 吻部（朝左前方）
        pygame.draw.polygon(screen, body, [(x + 2, y - 14), (x + 16, y - 30), (x + 24, y - 10)])
        # 尖耳朵（两枚）
        pygame.draw.polygon(screen, body, [(x + 6, y - 26), (x + 4, y - 38), (x + 12, y - 28)])
        pygame.draw.polygon(screen, body, [(x + 12, y - 26), (x + 13, y - 38), (x + 18, y - 27)])
        # 獠牙嘴（白色小三角）
        pygame.draw.polygon(screen, (225, 225, 230), [(x + 21, y - 8), (x + 25, y - 6), (x + 21, y - 4)])
        # 凶狠黄眼
        pygame.draw.circle(screen, (255, 205, 80), (x + 10, y - 17), 2)
        # 翘起的尾巴
        pygame.draw.line(screen, body, (x + self.w + 5, y - 2), (x + self.w + 16, y - 10), 3)
        pygame.draw.circle(screen, body, (x + self.w + 15, y - 11), 3)

    def _draw_brute(self, screen, body):
        """辐射蛮牛：厚重躯干 + 犄角 + 前突撞角，压迫感强。"""
        x, y = self.x, self.y
        # 厚重身体
        pygame.draw.rect(screen, body, (x, y - self.h // 2, self.w, self.h), border_radius=10)
        # 头部（左侧前方）
        pygame.draw.rect(screen, body, (x - 12, y - 20, 20, 28), border_radius=8)
        # 双犄角
        pygame.draw.polygon(screen, (210, 195, 160), [(x - 8, y - 16), (x - 18, y - 34), (x - 2, y - 18)])
        pygame.draw.polygon(screen, (210, 195, 160), [(x + 2, y - 18), (x - 4, y - 36), (x + 10, y - 20)])
        # 撞角（金属护额）
        pygame.draw.polygon(screen, (160, 150, 140), [(x - 14, y - 12), (x - 30, y + 2), (x - 10, y + 4)])
        # 眼睛（闷红）
        pygame.draw.circle(screen, (235, 90, 60), (x - 4, y - 12), 3)
        # 背部锈铁板
        pygame.draw.line(screen, (120, 110, 95), (x + 8, y - self.h // 2 + 3), (x + self.w - 8, y - self.h // 2 + 3), 3)

    def _draw_hexer(self, screen, body):
        """污染术士：紫色破旧斗篷 + 兜帽遮脸 + 漂浮姿态，只露出发光双眼。"""
        x, y = self.x, self.y
        # 斗篷主体（上窄下宽的三角）
        pygame.draw.polygon(screen, body, [(x + 3, y - 18), (x + self.w - 3, y - 18),
                                           (x + self.w + 4, y + self.h // 2 + 2), (x - 4, y + self.h // 2 + 2)])
        # 兜帽（圆弧）
        pygame.draw.circle(screen, (88, 54, 84), (x + self.w // 2, y - 20), 10)
        # 发光紫色双眼
        pygame.draw.circle(screen, (215, 120, 255), (x + self.w // 2 - 4, y - 20), 2)
        pygame.draw.circle(screen, (215, 120, 255), (x + self.w // 2 + 4, y - 20), 2)
        # 漂浮的袍摆 + 下方紫色光点
        pygame.draw.line(screen, body, (x - 4, y + self.h // 2 + 2), (x - 8, y + self.h // 2 + 8), 2)
        pygame.draw.line(screen, body, (x + self.w + 4, y + self.h // 2 + 2), (x + self.w + 8, y + self.h // 2 + 8), 2)
        pygame.draw.circle(screen, (170, 90, 220), (x + self.w // 2, y + self.h // 2 + 8), 2)

    def _draw_spitter(self, screen, body):
        """酸液喷射者：墨绿黏团 + 大嘴 + 滴落的酸液。"""
        x, y = self.x, self.y
        # 黏液身体（圆润）
        pygame.draw.ellipse(screen, body, (x, y - self.h // 2, self.w, self.h))
        pygame.draw.ellipse(screen, (88, 132, 78), (x + 4, y - self.h // 2 + 5, self.w - 8, self.h - 12))
        # 大嘴（朝左，张开的酸嘴）
        pygame.draw.ellipse(screen, (40, 66, 40), (x - 2, y - 4, 14, 10))
        # 滴落的酸液珠
        pygame.draw.circle(screen, (120, 200, 90), (x - 8, y + 6), 3)
        pygame.draw.circle(screen, (100, 180, 80), (x - 12, y + 12), 2)
        # 眼睛（黄）
        pygame.draw.circle(screen, (240, 230, 90), (x + self.w - 8, y - 8), 3)
        pygame.draw.circle(screen, (30, 40, 30), (x + self.w - 8, y - 8), 1)

    def _draw_raptor(self, screen, body):
        """裂爪迅猛龙：低伏冲刺姿态 + 头冠 + 尖尾 + 利爪。"""
        x, y = self.x, self.y
        # 低伏身体
        pygame.draw.ellipse(screen, body, (x - 6, y - 8, self.w + 12, self.h - 12))
        # 头 + 尖吻
        pygame.draw.polygon(screen, body, [(x - 2, y - 10), (x - 18, y - 4), (x - 4, y + 2)])
        # 头冠（红）
        pygame.draw.polygon(screen, (200, 90, 70), [(x - 2, y - 10), (x - 4, y - 22), (x + 4, y - 12)])
        # 眼睛
        pygame.draw.circle(screen, (255, 210, 90), (x - 6, y - 6), 2)
        # 尖尾
        pygame.draw.line(screen, body, (x + self.w + 5, y - 2), (x + self.w + 18, y - 8), 3)
        # 前爪利刃
        pygame.draw.line(screen, (200, 200, 205), (x - 2, y + 8), (x - 10, y + 14), 2)
        pygame.draw.line(screen, (200, 200, 205), (x + 2, y + 8), (x - 4, y + 15), 2)

    def _draw_frost(self, screen, body):
        """霜皮丧尸：覆盖冰晶甲片的蓝色丧尸，肩膀长冰刺。"""
        x, y = self.x, self.y
        # 身体（偏蓝已由 draw 统一处理 body）
        pygame.draw.rect(screen, body, (x, y - self.h // 2, self.w, self.h), border_radius=6)
        # 头部
        pygame.draw.circle(screen, body, (x + self.w // 2, y - self.h // 2 - 2), 8)
        # 冰晶肩甲（左右各一枚冰刺）
        pygame.draw.polygon(screen, (170, 225, 255), [(x - 2, y - 16), (x - 10, y - 30), (x + 6, y - 16)])
        pygame.draw.polygon(screen, (170, 225, 255), [(x + self.w - 4, y - 14), (x + self.w + 8, y - 26), (x + self.w + 6, y - 12)])
        # 暗淡蓝眼
        pygame.draw.circle(screen, (200, 235, 255), (x + self.w - 6, y - 8), 2)
        # 胸口冰晶
        pygame.draw.polygon(screen, (185, 235, 255), [(x + self.w // 2, y - 4), (x + self.w // 2 - 4, y + 6), (x + self.w // 2 + 4, y + 6)])

    def _draw_king(self, screen, body):
        """废土尸王：巨大尸骸 + 锈铁王冠 + 缠骨护甲 + 猩红眼，压迫感十足的boss。"""
        x, y = self.x, self.y
        # 庞大身体
        pygame.draw.rect(screen, body, (x, y - self.h // 2, self.w, self.h), border_radius=10)
        # 缠在身上的白骨（斜向肋骨）
        for i in range(3):
            pygame.draw.line(screen, (215, 210, 200), (x + 6 + i * 12, y - 16), (x + 18 + i * 12, y + 16), 3)
        # 头（左侧前方）+ 锈铁王冠
        pygame.draw.circle(screen, (70, 64, 74), (x - 6, y - self.h // 2), 11)
        pygame.draw.polygon(screen, (140, 120, 100), [(x - 16, y - self.h // 2 - 6), (x - 10, y - self.h // 2 - 20),
                                                      (x - 4, y - self.h // 2 - 8), (x + 2, y - self.h // 2 - 22),
                                                      (x + 8, y - self.h // 2 - 8)])
        # 猩红双眼
        pygame.draw.circle(screen, (255, 60, 50), (x - 10, y - self.h // 2 - 2), 3)
        pygame.draw.circle(screen, (255, 60, 50), (x - 2, y - self.h // 2 - 2), 3)
        # 锈铁肩甲
        pygame.draw.rect(screen, (110, 100, 90), (x - 8, y - 20, 12, 30), border_radius=4)
        pygame.draw.rect(screen, (110, 100, 90), (x + self.w - 6, y - 20, 12, 30), border_radius=4)
        # 腰间挂着的骷髅
        pygame.draw.circle(screen, (225, 220, 210), (x + self.w // 2, y + 16), 6)
        pygame.draw.circle(screen, (60, 54, 62), (x + self.w // 2 - 2, y + 14), 1)
        pygame.draw.circle(screen, (60, 54, 62), (x + self.w // 2 + 2, y + 14), 1)

    def _draw_colossus(self, screen, body):
        """装甲巨像：报废机甲改造的重装巨像，焊满装甲板，重拳砸击。"""
        x, y = self.x, self.y
        # 厚重装甲身体（灰蓝）
        pygame.draw.rect(screen, body, (x, y - self.h // 2, self.w, self.h), border_radius=6)
        # 胸前装甲板
        pygame.draw.rect(screen, (95, 105, 120), (x + 6, y - 10, self.w - 12, 14), border_radius=3)
        # 头部（金属头盔 + 红色目镜）
        pygame.draw.rect(screen, (60, 70, 85), (x + self.w // 2 - 7, y - self.h // 2 - 8, 14, 12), border_radius=3)
        pygame.draw.circle(screen, (255, 60, 40), (x + self.w // 2 - 3, y - self.h // 2 - 3), 2)
        pygame.draw.circle(screen, (255, 60, 40), (x + self.w // 2 + 3, y - self.h // 2 - 3), 2)
        # 重拳（向前挥）
        pygame.draw.rect(screen, (80, 90, 105), (x + self.w - 4, y - 14, 14, 22), border_radius=4)
        pygame.draw.rect(screen, (90, 100, 115), (x + self.w + 2, y - 14, 8, 22), border_radius=3)
        # 肩部铆钉
        pygame.draw.circle(screen, (110, 120, 135), (x - 2, y - 22), 4)
        pygame.draw.circle(screen, (110, 120, 135), (x + self.w + 2, y - 22), 4)

    def _draw_queen(self, screen, body):
        """尸巢母体：肿胀的变异母体，体表鼓起多个孵化囊，腹部蠕动发红。"""
        x, y = self.x, self.y
        # 臃肿身体（暗红）
        pygame.draw.ellipse(screen, body, (x - 2, y - self.h // 2, self.w + 6, self.h))
        # 孵化囊（身上鼓起的小圆包）
        for i in range(3):
            cx = x + 8 + i * 12
            pygame.draw.circle(screen, (140, 90, 95), (cx, y - 12 + (i % 2) * 6), 5)
            pygame.draw.circle(screen, (255, 120, 100), (cx, y - 12 + (i % 2) * 6), 2)
        # 头部（小 + 两侧触须）
        pygame.draw.circle(screen, (105, 60, 66), (x - 4, y - self.h // 2 - 4), 8)
        pygame.draw.line(screen, body, (x - 10, y - self.h // 2 - 8), (x - 20, y - self.h // 2 - 16), 2)
        pygame.draw.line(screen, body, (x + 4, y - self.h // 2 - 8), (x + 14, y - self.h // 2 - 18), 2)
        # 黄色眼
        pygame.draw.circle(screen, (250, 230, 120), (x - 7, y - self.h // 2 - 4), 2)
        # 腹部蠕动红光（呼吸闪烁）
        if (self.frames if hasattr(self, "frames") else 0) % 12 < 6:
            pygame.draw.ellipse(screen, (255, 90, 80), (x + self.w // 2 - 4, y + 10, 8, 6))

    def _draw_tyrant(self, screen, body):
        """废土暴君：金属骨甲覆身的辐射霸主，尖刺肩甲 + 巨型重锤，压迫感强。"""
        x, y = self.x, self.y
        # 魁梧身体
        pygame.draw.rect(screen, body, (x, y - self.h // 2, self.w, self.h), border_radius=8)
        # 金属骨甲（斜向骨刺护甲）
        for i in range(4):
            pygame.draw.line(screen, (150, 140, 135), (x + 4 + i * 11, y - 18), (x + 14 + i * 11, y + 20), 3)
        # 尖刺肩甲
        pygame.draw.polygon(screen, (120, 110, 105), [(x - 4, y - 20), (x - 14, y - 36), (x + 8, y - 20)])
        pygame.draw.polygon(screen, (120, 110, 105), [(x + self.w + 4, y - 18), (x + self.w + 16, y - 34), (x + self.w - 6, y - 18)])
        # 头部 + 猩红独眼
        pygame.draw.circle(screen, (66, 58, 70), (x + self.w // 2, y - self.h // 2 - 4), 9)
        pygame.draw.circle(screen, (255, 30, 30), (x + self.w // 2, y - self.h // 2 - 4), 3)
        # 巨型重锤
        pygame.draw.rect(screen, (90, 84, 80), (x + self.w - 2, y - 8, 20, 10), border_radius=3)
        pygame.draw.rect(screen, (120, 112, 106), (x + self.w + 12, y - 16, 14, 26), border_radius=3)

    def _draw_leviathan(self, screen, body):
        """辐射利维坦：盘踞废土的巨型辐射巨兽（横跨全部行），巨口獠牙 + 背鳍 + 尾刺。"""
        x, y = self.x, self.y
        # 巨型身躯（纵向覆盖整列高度）
        pygame.draw.ellipse(screen, body, (x - self.w // 2, y - CELL_H * 2.6, self.w, CELL_H * 5.2))
        # 背部辐射鳍（一列锯齿鳍）
        for i in range(5):
            fx = x + self.w // 2 - 2 + i * 3 - 6
            pygame.draw.polygon(screen, (90, 130, 130), [(fx, y - CELL_H * 2.4), (fx + 4, y - CELL_H * 3.0), (fx + 8, y - CELL_H * 2.4)])
        # 头部巨口（前方）
        pygame.draw.ellipse(screen, body, (x - 22, y - 30, 40, 26))
        pygame.draw.polygon(screen, (220, 225, 230), [(x - 18, y - 18), (x - 12, y - 30), (x - 8, y - 18)])   # 獠牙上
        pygame.draw.polygon(screen, (220, 225, 230), [(x - 18, y + 6), (x - 12, y + 16), (x - 8, y + 6)])       # 獠牙下
        pygame.draw.circle(screen, (255, 220, 90), (x - 16, y - 6), 5)                                          # 巨眼
        pygame.draw.circle(screen, (60, 30, 20), (x - 16, y - 6), 2)
        # 尾部
        pygame.draw.line(screen, body, (x + self.w // 2 + 2, y), (x + self.w // 2 + 26, y + 6), 8)
        pygame.draw.polygon(screen, (90, 130, 130), [(x + self.w // 2 + 20, y + 2), (x + self.w // 2 + 34, y - 8), (x + self.w // 2 + 30, y + 14)])

    def _draw_giant(self, screen):
        """末日终结者：巨型废土装甲巨兽，身体横跨全部5行（约470像素高）。"""
        c0 = self.color
        # 冰元素状态（寒冷/冻结/冻伤）：身体整体偏蓝
        if self.cold_timer > 0 or self.freeze_timer > 0 or self.frost_timer > 0:
            c0 = (min(c0[0] + 40, 255), max(c0[1] - 20, 25), min(c0[2] + 90, 255))
        top = self.y - CELL_H * 2.5                       # 身体顶部（网格顶）
        # 身体主体（装甲柱）
        pygame.draw.rect(screen, c0, (self.x, int(top), 66, 5 * CELL_H), border_radius=12)
        # 装甲板横线 + 两侧铆钉
        for r in range(5):
            yc = int(top) + r * CELL_H
            pygame.draw.line(screen, (70, 78, 96), (self.x + 4, yc), (self.x + 62, yc), 2)
            pygame.draw.circle(screen, (95, 105, 125), (self.x + 8, yc + CELL_H // 2), 3)
            pygame.draw.circle(screen, (95, 105, 125), (self.x + 58, yc + CELL_H // 2), 3)
        # 中央能源核心（发光红核）
        pygame.draw.circle(screen, (200, 55, 35), (self.x + 33, self.y), 18)
        pygame.draw.circle(screen, (255, 110, 70), (self.x + 33, self.y), 9)
        # 肩甲 + 机械臂
        pygame.draw.rect(screen, (48, 54, 66), (self.x - 16, self.y - 46, 20, 92), border_radius=8)
        pygame.draw.rect(screen, (48, 54, 66), (self.x + 62, self.y - 46, 20, 92), border_radius=8)
        # 头部（顶部）：带角头盔 + 发光眼
        hx, hy = self.x + 33, int(top) + 22
        pygame.draw.rect(screen, (52, 58, 72), (hx - 28, hy - 12, 56, 40), border_radius=10)
        pygame.draw.polygon(screen, (62, 68, 82), [(hx - 24, hy - 10), (hx - 34, hy - 32), (hx - 12, hy - 10)])
        pygame.draw.polygon(screen, (62, 68, 82), [(hx + 24, hy - 10), (hx + 34, hy - 32), (hx + 12, hy - 10)])
        pygame.draw.circle(screen, (255, 80, 50), (hx - 13, hy + 2), 6)
        pygame.draw.circle(screen, (255, 80, 50), (hx + 13, hy + 2), 6)
        # 冻结：头部被冰框封住
        if self.freeze_timer > 0:
            pygame.draw.rect(screen, (170, 225, 255), (hx - 32, hy - 16, 64, 48), 3, border_radius=6)
        # 血条 + 血量数字（画在身体最上端第一行内，避免与HUD重叠）
        rate = self.hp / self.maxhp
        bw = 120
        bx = self.x + 33 - bw // 2
        by = int(top) + 48
        pygame.draw.rect(screen, (70, 70, 70), (bx, by, bw, 7))
        pygame.draw.rect(screen, (255, 60, 60), (bx, by, bw * max(rate, 0), 7))
        key = f"{int(self.hp)}/{self.maxhp}"
        if getattr(self, "_g_hp_key", None) != key:
            self._g_hp_key = key
            self._g_hp_img = make_font(12).render(key, True, COLOR_TEXT)
        screen.blit(self._g_hp_img, (bx - self._g_hp_img.get_width() - 6, by - 2))

    def _draw_giant_mini(self, screen):
        """迷你版末日终结者：沙盒顶部怪物面板的小图标（不画血条，避免溢出面板）。"""
        cx, cy = self.x, self.y
        body_w, body_h = 34, 30
        top = cy - body_h // 2
        pygame.draw.rect(screen, self.color, (cx - body_w // 2, top, body_w, body_h), border_radius=6)
        for r in range(3):                                      # 装甲横线
            yc = top + r * (body_h // 3)
            pygame.draw.line(screen, (70, 78, 96), (cx - body_w // 2 + 2, yc),
                             (cx + body_w // 2 - 2, yc), 1)
        pygame.draw.circle(screen, (255, 110, 70), (cx, cy), 6)  # 中央能源核心
        hx, hy = cx, top - 1
        pygame.draw.rect(screen, (52, 58, 72), (hx - 10, hy - 11, 20, 15), border_radius=5)
        pygame.draw.polygon(screen, (62, 68, 82), [(hx - 8, hy - 9), (hx - 12, hy - 18), (hx - 3, hy - 9)])
        pygame.draw.polygon(screen, (62, 68, 82), [(hx + 8, hy - 9), (hx + 12, hy - 18), (hx + 3, hy - 9)])
        pygame.draw.circle(screen, (255, 80, 50), (hx - 5, hy - 3), 2)
        pygame.draw.circle(screen, (255, 80, 50), (hx + 5, hy - 3), 2)


# ============================================================================
# 八、行动顺序系统区
# ============================================================================
# 【说明】实现“行动顺序系统”：所有我方单位与怪物都有一个累积值 action，
#         每帧 action += speed；当 action >= 100 时执行一次“行动帧”并扣减100。
#         speed 越大行动越频繁，形成不同单位/怪物的行动节奏差异。
class ActionSystem:
    def __init__(self):
        pass

    @staticmethod
    def tick(entities, ctx, mouse_pos):
        """
        推进所有实体的行动累积。entities 是所有可行动对象（我方+怪物）。
        返回：一轮中实际“行动”过的实体数量（仅用于诊断/节奏）。
        """
        acted = 0
        for e in entities:
            e.action += e.speed
            while e.action >= 100:
                e.action -= 100
                acted += 1
        return acted

# ============================================================================
# 九、场景区：加载 / 主菜单 / 手册 / 卡牌选择 / 战斗
# ============================================================================
# 【说明】每个场景类统一接口：
#   handle_event(event)  处理输入
#   update()             更新逻辑（每帧）
#   draw(screen)         绘制
#   主循环按 game.scene 找到对应场景并调用三件套。
#   【后续新增界面】新增一个类并实现这三件套，再到主循环登记即可。

# ---------------------------------------------------------------
# 9.1 加载界面：模拟加载资源，完成后跳主菜单
# ---------------------------------------------------------------
class LoadScene:
    def __init__(self, game):
        self.game = game
        self.tick = 0

    def handle_event(self, event):
        pass

    def update(self):
        self.tick += 1
        if self.tick >= LOAD_TOTAL_TICKS:
            self.game.scene = "menu"

    def draw(self, screen):
        screen.fill(COLOR_BG)
        title = make_font(46).render("废土耕地者", True, COLOR_GOLD)
        sub = make_font(22).render("Sinkland Cultivator", True, COLOR_TEXT_DIM)
        screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 200))
        screen.blit(sub, (SCREEN_WIDTH//2 - sub.get_width()//2, 260))
        # 进度条
        p = min(self.tick / LOAD_TOTAL_TICKS, 1.0)
        pygame.draw.rect(screen, COLOR_PANEL, (200, 340, SCREEN_WIDTH - 400, 20), border_radius=10)
        pygame.draw.rect(screen, COLOR_GOLD, (200, 340, (SCREEN_WIDTH - 400) * p, 20), border_radius=10)
        tip = make_font(18).render("正在加载基地资源…", True, COLOR_TEXT_DIM)
        screen.blit(tip, (SCREEN_WIDTH//2 - tip.get_width()//2, 375))

# ---------------------------------------------------------------
# 9.2 主菜单界面：只有 设置 / 关卡 / 图鉴 三个入口
# ---------------------------------------------------------------
class MenuScene:
    def __init__(self, game):
        self.game = game
        b = make_font(22)
        w, h = 260, 58
        # 两列布局：第一列(左) = 关卡 / 无尽模式 / 沙盒模式；第二列(右) = 指南 / 图鉴 / 设置
        col_w = w * 2 + 30                       # 两列总宽
        x1 = SCREEN_WIDTH // 2 - col_w // 2      # 第一列按钮左边缘
        x2 = x1 + w + 30                         # 第二列按钮左边缘
        ys = [200, 300, 400]                     # 三行垂直位置
        self.btns = [
            Button(x1, ys[0], w, h, "关  卡", lambda: self.goto("level"), b),
            Button(x1, ys[1], w, h, "无尽模式", self.start_endless, b),
            Button(x1, ys[2], w, h, "沙盒模式", lambda: self.goto("sandbox"), b),
            Button(x2, ys[0], w, h, "指  南", lambda: self.goto("guide"), b),
            Button(x2, ys[1], w, h, "图  鉴", lambda: self.goto("codex"), b),
            Button(x2, ys[2], w, h, "设  置", lambda: self.goto("settings"), b),
        ]

    def goto(self, name): self.game.scene = name
    def start_endless(self):
        """进入无尽模式：有存档则恢复阵容与关卡进度继续，无存档则从第1关新开（先选卡再进战斗）。"""
        g = self.game
        g.endless_mode = True
        if not g.load_endless_snapshot():
            # 无存档：新开无尽从第1关
            g.endless_stage = 1
            g.endless_keep_units = []
            g.endless_energy = 0
        g.selected_cards = []
        g.scene = "card"

    def handle_event(self, event):
        for b in self.btns: b.handle_event(event)

    def update(self): pass

    def draw(self, screen):
        screen.fill(COLOR_BG)
        title = make_font(56).render("废土耕地者", True, COLOR_GOLD)
        sub = make_font(20).render("Sinkland Cultivator", True, COLOR_TEXT_DIM)
        screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 100))
        screen.blit(sub, (SCREEN_WIDTH//2 - sub.get_width()//2, 165))
        for b in self.btns: b.draw(screen)

# ---------------------------------------------------------------
# 9.2.0 指南界面：教基础操作（部署/铲除/大招/能量/加速/模式说明）
# ---------------------------------------------------------------
class GuideScene:
    """操作指南：多行说明文本 + 滚轮上下滚动 + 返回按钮。"""
    def __init__(self, game):
        self.game = game
        b = make_font(20)
        self.back = Button(30, SCREEN_HEIGHT - 70, 150, 50, "返回主菜单",
                           lambda: setattr(game, "scene", "menu"), b)
        self.scroll = 0                     # 文本垂直滚动偏移（负值显示更靠后的内容）
        self.row_h = 30                     # 每行高度（标题行稍高，绘制时用大字号）
        self.top, self.bottom = 100, SCREEN_HEIGHT - 90   # 文本可视区（上下边界）
        # 说明内容：每项 (文本, 是否小标题)。标题金色加粗，正文普通色。
        self.items = [
            ("【部署单位】", True),
            ("· 点底部卡槽选中卡牌，再点战场网格格子放置", False),
            ("· 快捷键：鼠标移到格子，按数字键 1~0 直接放置卡槽第 1~10 张对应角色", False),
            ("· SP 角色必须先种下普通形态，再把 SP 卡种到其上原地替换升级", False),
            ("", False),
            ("【铲除单位】", True),
            ("· 点顶部【休憩令】按钮拿起铲子，再点场上的单位铲除（再点按钮收回）", False),
            ("· 快捷键：鼠标移到格子，按 Backspace 直接铲除该格角色", False),
            ("", False),
            ("【释放大招】", True),
            ("· 鼠标对准我方单位，按【空格】释放大招（每局共 5 次机会）", False),
            ("· 烬/烬SP 没有大招；烬SP 按空格切换火/冰/毒三种形态", False),
            ("", False),
            ("【能量】", True),
            ("· 能量由里昂等能源单位产出：能源球生成后 1 秒内自动飞向顶部能量栏自动拾取", False),
            ("· 部署每个单位都会消耗能量，能量不足时无法放置", False),
            ("", False),
            ("【战斗加速】", True),
            ("· 右上角【加速 ×N】按钮让全场单位与怪物行动速度翻倍", False),
            ("", False),
            ("【模式说明】", True),
            ("· 测试模式：无限能量、部署无冷却、大招无冷却（在设置里开启）", False),
            ("· 无尽模式：每关 2 小波、怪物扎堆出；转关保留上一关布局并重新选卡；", False),
            ("  关闭程序后存档仍可恢复阵容与关卡进度", False),
            ("· 注意：无尽模式打到后面怪物太多、画面变卡属正常现象；", False),
            ("  转关/选关时不要一次输入太多关数，否则可能导致卡死", False),
            ("· 沙盒模式：可自由放置所有角色与所有怪物，用于调试阵容与测试技能", False),
            ("", False),
            ("【增益与状态】", True),
            ("· 鼠标移到角色/怪物上，会显示名字、血条与当前增益/减益明细", False),
            ("· 伤害数字按元素配色：物理灰 / 火红 / 冰蓝 / 雷紫 / 毒绿 / 水青", False),
        ]

    def max_scroll(self):
        """内容总高超出可视区时的最大滚动偏移（≥0）。"""
        return max(0, len(self.items) * self.row_h - (self.bottom - self.top))

    def handle_event(self, event):
        self.back.handle_event(event)
        # 滚轮上下滚动说明文本
        if event.type == pygame.MOUSEWHEEL:
            self.scroll += event.y * self.row_h
            self.scroll = max(-self.max_scroll(), min(0, self.scroll))

    def update(self):
        pass

    def draw(self, screen):
        screen.fill(COLOR_BG)
        title = make_font(38).render("操作指南", True, COLOR_GOLD)
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 30))
        hint = make_font(16).render("使用鼠标滚轮上下滚动", True, COLOR_TEXT_DIM)
        screen.blit(hint, (SCREEN_WIDTH - hint.get_width() - 30, 40))
        # 逐行绘制（按滚动偏移，超界裁剪）
        yy = self.top + self.scroll
        for text, is_title in self.items:
            if yy + self.row_h < self.top:      # 还在可视区上方，跳过
                yy += self.row_h
                continue
            if yy > self.bottom:                # 已滚出可视区下方，停止
                break
            color = COLOR_GOLD if is_title else COLOR_TEXT
            size = 22 if is_title else 18
            t = make_font(size).render(text, True, color)
            screen.blit(t, (60, yy + 4))
            yy += self.row_h
        self.back.draw(screen)

# ---------------------------------------------------------------
# 9.2.1 设置界面：音乐 / 音量 / 难度 / 测试模式
# ---------------------------------------------------------------
class SettingsScene:
    def __init__(self, game):
        self.game = game
        b = make_font(20)
        self.toggle_music = Button(200, 150, 220, 52, "音乐：开", self.tog_music, b)
        self.toggle_diff  = Button(200, 220, 220, 52, "难度：普通", self.tog_diff, b)
        self.toggle_cheat = Button(200, 290, 220, 52, "测试：关", self.tog_cheat, b)
        self.vol_down = Button(200, 360, 100, 46, "音量-", self.vol_minus, b)
        self.vol_up   = Button(320, 360, 100, 46, "音量+", self.vol_plus, b)
        self.back = Button(SCREEN_WIDTH//2 - 100, 470, 200, 52, "返回主界面", self.goto_menu, b)

    def goto_menu(self): self.game.scene = "menu"
    def tog_music(self): self.game.music_on = not self.game.music_on
    def tog_cheat(self): self.game.cheat = not self.game.cheat
    def tog_diff(self):
        order = ["简单", "普通", "困难"]
        i = order.index(self.game.difficulty)
        self.game.difficulty = order[(i + 1) % 3]
    def vol_minus(self): self.game.volume = max(0, self.game.volume - 10)
    def vol_plus(self): self.game.volume = min(100, self.game.volume + 10)

    def handle_event(self, event):
        self.toggle_music.handle_event(event)
        self.toggle_diff.handle_event(event)
        self.toggle_cheat.handle_event(event)
        self.vol_down.handle_event(event)
        self.vol_up.handle_event(event)
        self.back.handle_event(event)

    def update(self):
        self.toggle_music.text = "音乐：" + ("开" if self.game.music_on else "关")
        self.toggle_diff.text = "难度：" + self.game.difficulty
        self.toggle_cheat.text = "测试：" + ("开" if self.game.cheat else "关")

    def draw(self, screen):
        screen.fill(COLOR_BG)
        title = make_font(38).render("设置", True, COLOR_GOLD)
        screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 40))
        vol = make_font(20).render(f"音量：{self.game.volume}", True, COLOR_TEXT_DIM)
        screen.blit(vol, (440, 372))
        self.toggle_music.draw(screen)
        self.toggle_diff.draw(screen)
        self.toggle_cheat.draw(screen)
        self.vol_down.draw(screen)
        self.vol_up.draw(screen)
        self.back.draw(screen)

# ---------------------------------------------------------------
# 9.2.2 关卡选择界面：全部关卡直接可选
# ---------------------------------------------------------------
class LevelSelectScene:
    def __init__(self, game):
        self.game = game
        b = make_font(20)
        # 4列布局：10个普通关卡 = 3行（4+4+2），全部可见无需滚动（按钮 260×68，行距88）
        self.level_btns = []
        for i, lv in enumerate(LEVELS):
            x = 75 + (i % 4) * 290
            y = 135 + (i // 4) * 88
            self.level_btns.append(
                Button(x, y, 260, 68, lv["name"],
                       (lambda idx=i: self.choose(idx)), b))
        # 三个特殊入口：测试关 / DPS试炼场（无需选卡，直接进测试场景）/ 返回
        self.test_btn = Button(40, 430, 220, 56, "测试关 · 末日终结者", self.choose_test, b)
        self.dps_btn = Button(280, 430, 220, 56, "DPS 试炼场", self.choose_dps, b)
        self.back = Button(520, 430, 260, 56, "返回主界面", self.goto_menu, b)

    def goto_menu(self): self.game.scene = "menu"
    def choose(self, idx):
        self.game.selected_level = idx
        self.game.scene = "card"     # 选关后直接进入选卡

    def choose_test(self):
        """进入测试关：选中末日终结者关卡（标记 -1），照常选卡后进战斗。"""
        self.game.selected_level = -1
        self.game.scene = "card"

    def choose_dps(self):
        """进入 DPS 试炼场：能量/冷却/大招全开，最后面一排沙包统计总伤害与 DPS。"""
        self.game.dps_mode = True
        self.game.selected_level = 0
        self.game.scene = "battle"

    def handle_event(self, event):
        for b in self.level_btns: b.handle_event(event)
        self.test_btn.handle_event(event)
        self.dps_btn.handle_event(event)
        self.back.handle_event(event)

    def update(self): pass

    def draw(self, screen):
        screen.fill(COLOR_BG)
        title = make_font(38).render("选择关卡", True, COLOR_GOLD)
        screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 30))
        hint = make_font(17).render("所有关卡均已解锁，直接点击选择 · 关卡规则会改变战场环境", True, COLOR_TEXT_DIM)
        screen.blit(hint, (SCREEN_WIDTH//2 - hint.get_width()//2, 85))
        for b in self.level_btns: b.draw(screen)
        self.test_btn.draw(screen)
        self.dps_btn.draw(screen)
        if self.game.selected_level is not None and self.game.selected_level != -1:
            lv = LEVELS[self.game.selected_level]
            info = make_font(18).render(f"当前选择：{lv['name']}", True, COLOR_GOLD)
            screen.blit(info, (80, 500))
            if lv.get("rule_desc"):
                rd = make_font(16).render(f"本关规则：{lv['rule_desc']}", True, (255, 190, 90))
                screen.blit(rd, (80, 530))
        self.back.draw(screen)

# ---------------------------------------------------------------
# 9.3 手册界面：我方单位图鉴 + 怪物图鉴
# ---------------------------------------------------------------
class CodexScene:
    def __init__(self, game):
        self.game = game
        self.tab = "unit"            # "unit" 我方 / "monster" 怪物
        self.sel = 0                 # 当前查看的第几条
        b = make_font(20)
        self.back = Button(40, SCREEN_HEIGHT - 60, 140, 44, "返回主菜单", self.goto_menu, b)
        self.tab_units = Button(120, 80, 180, 44, "我方单位", self.sw_unit, b)
        self.tab_monsters = Button(320, 80, 180, 44, "怪物图鉴", self.sw_monster, b)
        self.prev = Button(560, SCREEN_HEIGHT - 60, 120, 44, "上一个", self.prev_item, b)
        self.next = Button(700, SCREEN_HEIGHT - 60, 120, 44, "下一个", self.next_item, b)

    def goto_menu(self): self.game.scene = "menu"
    def sw_unit(self): self.tab = "unit"; self.sel = 0
    def sw_monster(self): self.tab = "monster"; self.sel = 0
    def prev_item(self): self.sel = max(0, self.sel - 1)
    def next_item(self):
        data = UNITS if self.tab == "unit" else MONSTERS
        self.sel = min(len(data) - 1, self.sel + 1)

    def handle_event(self, event):
        self.back.handle_event(event)
        self.tab_units.handle_event(event)
        self.tab_monsters.handle_event(event)
        self.prev.handle_event(event)
        self.next.handle_event(event)

    def update(self): pass

    def draw(self, screen):
        screen.fill(COLOR_BG)
        title = make_font(40).render("图鉴手册", True, COLOR_GOLD)
        screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 20))
        self.tab_units.draw(screen)
        self.tab_monsters.draw(screen)
        data = UNITS if self.tab == "unit" else MONSTERS
        if not data:
            return
        d = data[self.sel]
        # 名称区（SP 变体加标记）
        nm_txt = d["name"] + ("（SP 进阶）" if d.get("is_sp") else "")
        name = make_font(34).render(nm_txt, True, COLOR_WHITE)
        screen.blit(name, (80, 150))
        # 属性区
        f = make_font(20)
        lines = []
        if self.tab == "unit":
            beh = {"energy": "能源生产", "shooter": "远程输出", "blocker": "肉盾阻挡",
                   "fire": "火焰爆破", "melee": "近战切割", "ice": "冰霜控制",
                   "healer": "治疗支援", "pierce": "贯穿输出", "chain": "雷电范围输出"}.get(d["behavior"], d["behavior"])
            hp_txt = "无（投掷后消失）" if d.get("behavior") == "fire" else str(d['hp'])
            lines = [
                f"生命：{hp_txt}",
                f"部署消耗：{d['cost']} 能量    冷却：{d['cd']}秒",
                f"定位：{beh}",
            ]
            if d.get("dmg_reduce"):
                lines.append(f"常驻减伤：{int(d['dmg_reduce'] * 100)}%")
            if d.get("produce_iv"):
                lines.append(f"能源产出：每{d['produce_iv']}秒 +{d['produce']}")
            if d.get("attack"):
                lines.append(f"攻击力：{d['attack']}    攻击间隔：{d['atk_iv']}秒")
            lines.append(f"大招【{d['ult_name']}】：{d['ult_desc']}")
        else:
            lines = [
                f"生命：{d['hp']}",
                f"移动速度：{d['speed']}",
                f"啃咬伤害：{d['atk']}",
            ]
        lines.append("—— " + d["desc"] + " ——")
        y = 210
        for ln in lines:
            img = f.render(ln, True, COLOR_TEXT)
            screen.blit(img, (80, y))
            y += 34
        # 形象区：右侧大图（我方单位用完整战斗形象，怪物用独立外形；末日终结者画缩小版）
        cx, cy = 880, 330
        if self.tab == "unit":
            try:
                dd = Defender(d["uid"], cx, cy)
                dd.draw(screen)
            except Exception:
                pass
        else:
            if d.get("giant"):
                # 缩小版末日终结者（图鉴页放不下整只 470 高，画迷你版）
                c0 = d["color"]
                pygame.draw.rect(screen, c0, (cx - 33, cy - 100, 66, 200), border_radius=12)
                for r in range(4):
                    yc = cy - 100 + r * 50
                    pygame.draw.line(screen, (70, 78, 96), (cx - 29, yc), (cx + 29, yc), 2)
                pygame.draw.circle(screen, (200, 55, 35), (cx, cy - 10), 16)
                pygame.draw.circle(screen, (255, 110, 70), (cx, cy - 10), 8)
                pygame.draw.rect(screen, (52, 58, 72), (cx - 26, cy - 128, 52, 40), border_radius=10)
                pygame.draw.circle(screen, (255, 80, 50), (cx - 12, cy - 116), 6)
                pygame.draw.circle(screen, (255, 80, 50), (cx + 12, cy - 116), 6)
            else:
                mm = Monster(d["uid"], 0)
                mm.x, mm.y = cx, cy
                mm.draw(screen)
        # 形象标签（区分SP/护甲怪）
        tag = ""
        if d.get("is_sp"):
            tag = "SP 进阶形态"
        elif d.get("armor"):
            tag = {"shield": "护盾单位", "tank": "护甲单位", "scrap": "碎片护甲"}.get(d["armor_type"], "护甲单位")
        if tag:
            tg = make_font(18).render(tag, True, COLOR_GOLD)
            screen.blit(tg, (cx - tg.get_width() // 2, cy + 130))
        # 翻页指示
        idx = make_font(18).render(f"{self.sel + 1} / {len(data)}", True, COLOR_TEXT_DIM)
        screen.blit(idx, (80, y + 10))
        self.prev.draw(screen)
        self.next.draw(screen)
        self.back.draw(screen)

# ---------------------------------------------------------------
# 9.4 卡牌选择界面：10 槽位，全部卡牌自由选择
# ---------------------------------------------------------------
class CardSelectScene:
    def __init__(self, game):
        self.game = game
        b = make_font(20)
        self.start_btn = Button(SCREEN_WIDTH//2 - 100, SCREEN_HEIGHT - 70, 200, 50, "开始战斗", self.start_battle, b)
        self.back_btn = Button(30, SCREEN_HEIGHT - 70, 140, 50, "返回主菜单", self.goto_menu, b)
        self.slots = list(game.selected_cards) if game.selected_cards else []
        self.msg = ""
        self.scroll = 0            # 卡牌池滚动偏移（像素），滚轮上下滚动查看全部卡牌
        # 卡牌池可视区（y 从 110 到 395，约 280px 高）
        self.pool_vis_top, self.pool_vis_bot = 110, 395
        self.pool_rows = (len(UNITS) + 3) // 4          # 池总行数
        self.pool_max_scroll = max(0, self.pool_rows * 120 - (self.pool_vis_bot - self.pool_vis_top))
        # ---- 无尽模式：目标关卡（进下一关时可选择直接打第几关） ----
        # 默认 = 顺序递增的下一关（game.endless_stage）；玩家可用 [－]/[＋] 步进，
        # 或点击数字框直接输入任意大关数，开始战斗即挑战该关（数量/血量/种类按该关计算）。
        self.target_stage = game.endless_stage if game.endless_mode else 1
        self.target_input_active = False       # 是否正在输入目标关数
        self.target_input_text = ""            # 正在输入的数字文本
        f = make_font(15)
        self.tminus_btn = Button(SCREEN_WIDTH - 330, 26, 28, 26, "－", lambda: self.adj_target(-1), f)
        self.tplus_btn  = Button(SCREEN_WIDTH - 74, 26, 28, 26, "＋", lambda: self.adj_target(1), f)
        self.target_box = pygame.Rect(SCREEN_WIDTH - 296, 26, 210, 26)

    def goto_menu(self):
        self.game.reset_endless()          # 退出无尽模式（下次重新开始）
        self.game.scene = "menu"
    def start_battle(self):
        if not self.slots:
            self.msg = "请至少选择1张卡牌"
            return
        if self.game.selected_level is None and not self.game.endless_mode:
            self.msg = "请先在关卡界面选择一个关卡"
            return
        self.game.selected_cards = self.slots
        if self.game.endless_mode:
            # 无尽模式：把目标关卡写回 game.endless_stage（支持直接跳到任意关卡挑战）
            self.game.endless_stage = max(1, self.target_stage)
        self.game.scene = "battle"

    def adj_target(self, delta):
        """无尽模式：步进调整目标关卡（最小1，可调任意大关数）。"""
        self.target_stage = max(1, self.target_stage + delta)
        self.target_input_active = False
        self.target_input_text = ""

    def handle_event(self, event):
        self.start_btn.handle_event(event)
        self.back_btn.handle_event(event)
        # 无尽模式：目标关卡调节（[－]/[＋] 步进 + 点击数字框直接输入任意关数）
        if self.game.endless_mode:
            self.tminus_btn.handle_event(event)
            self.tplus_btn.handle_event(event)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.target_box.collidepoint(event.pos):
                    self.target_input_active = True
                    self.target_input_text = ""
            elif event.type == pygame.KEYDOWN and self.target_input_active:
                if event.key == pygame.K_BACKSPACE:
                    self.target_input_text = self.target_input_text[:-1]
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    if self.target_input_text.isdigit():
                        self.target_stage = max(1, int(self.target_input_text))
                    self.target_input_active = False
                elif event.key in range(pygame.K_0, pygame.K_9 + 1) and len(self.target_input_text) < 5:
                    self.target_input_text += chr(event.key)
        # 鼠标滚轮：上下滚动卡牌池（只对池区域生效）
        if event.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, min(self.pool_max_scroll, self.scroll - event.y * 30))
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            # 卡牌池区（上方网格，随滚动偏移）：点击添加卡牌到槽位
            pool_x, pool_y = 80, 110
            for i, u in enumerate(UNITS):
                if len(self.slots) >= 10:
                    break
                card = pygame.Rect(pool_x + (i % 4) * 200,
                                   pool_y + (i // 4) * 120 - self.scroll, 180, 100)
                if (card.y >= self.pool_vis_top and card.y <= self.pool_vis_bot
                        and card.collidepoint((mx, my))
                        and u["uid"] not in [s["uid"] for s in self.slots]):
                    self.slots.append(u)
            # 槽位区（底部，整体居中）：点击移除
            slot_x0 = (SCREEN_WIDTH - 920) // 2
            for i, s in enumerate(self.slots):
                slot = pygame.Rect(slot_x0 + i * 92, 440, 88, 88)
                if slot.collidepoint((mx, my)):
                    self.slots.pop(i)

    def update(self): pass

    def draw(self, screen):
        screen.fill(COLOR_BG)
        # 卡牌池（先画，用裁剪限制在可视区内，滚动时不会遮住标题和提示文字）
        pool_x, pool_y = 80, 110
        screen.set_clip((pool_x, self.pool_vis_top, 800, self.pool_vis_bot - self.pool_vis_top))
        for i, u in enumerate(UNITS):
            card = pygame.Rect(pool_x + (i % 4) * 200,
                               pool_y + (i // 4) * 120 - self.scroll, 180, 100)
            if card.bottom < self.pool_vis_top or card.y > self.pool_vis_bot:
                continue
            pygame.draw.rect(screen, COLOR_PANEL, card, border_radius=8)
            pygame.draw.rect(screen, COLOR_GRID, card, 2, border_radius=8)
            n = make_font(22).render(u["name"], True, COLOR_WHITE)
            c = make_font(16).render(f"能量 {u['cost']}", True, COLOR_GOLD)
            screen.blit(n, (card.x + 10, card.y + 8))
            screen.blit(c, (card.x + 10, card.y + 38))
            # 卡牌中央显示角色的完整 Q 版形象
            draw_unit_icon(screen, u, card.x + 132, card.y + 60, (62, 76))
        screen.set_clip(None)
        # 滚动提示 + 滚动条（卡牌多时可上下滚动）
        if self.pool_max_scroll > 0:
            tip2 = make_font(15).render("↑ 滚轮上下滚动查看更多卡牌 ↓", True, COLOR_TEXT_DIM)
            screen.blit(tip2, (80, 93))
            bar_h = max(24, int(280 * 280 / (self.pool_rows * 120)))
            bar_y = 110 + int((280 - bar_h) * self.scroll / self.pool_max_scroll)
            pygame.draw.rect(screen, (55, 55, 62), (SCREEN_WIDTH - 30, 110, 6, 280))
            pygame.draw.rect(screen, COLOR_GOLD, (SCREEN_WIDTH - 30, bar_y, 6, bar_h))
        # 标题与提示文字最后绘制（始终显示在最上层，不被卡牌遮挡）
        if self.game.endless_mode:
            title_txt = f"无尽模式 · 第 {self.target_stage} 关选卡"
            keep_n = len(self.game.endless_keep_units)
            hint_txt = (f"点击卡牌加入槽位（最多10张）；场上已有 {keep_n} 个单位将保留，点击槽位移除卡牌"
                        if keep_n else "点击卡牌加入槽位（最多10张）；建议带上里昂产出能源，点击槽位移除卡牌")
        else:
            title_txt = "战前选卡"
            hint_txt = "点击卡牌加入槽位（最多10张）；建议带上里昂产出能源，点击槽位移除卡牌"
        title = make_font(38).render(title_txt, True, COLOR_GOLD)
        screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 20))
        hint = make_font(18).render(hint_txt, True, COLOR_TEXT_DIM)
        screen.blit(hint, (80, 70))
        # 无尽模式：目标关卡调节控件（始终绘制在最上层，不被卡牌池遮挡）
        if self.game.endless_mode:
            self.tminus_btn.draw(screen)
            self.tplus_btn.draw(screen)
            boxc = COLOR_BUTTON_H if self.target_box.collidepoint(pygame.mouse.get_pos()) else COLOR_BUTTON
            pygame.draw.rect(screen, boxc, self.target_box, border_radius=6)
            pygame.draw.rect(screen, COLOR_GOLD if self.target_input_active else COLOR_GRID,
                             self.target_box, 2, border_radius=6)
            if self.target_input_active:
                t = (self.target_input_text or "_")
                tc = COLOR_GOLD
            else:
                t = f"目标关卡：第 {self.target_stage} 关"
                tc = COLOR_WHITE
            timg = make_font(15).render(t, True, tc)
            screen.blit(timg, (self.target_box.x + 8, self.target_box.centery - timg.get_height() // 2))
        # 槽位（底部10格，整体居中）
        slot_x0 = (SCREEN_WIDTH - 920) // 2
        for i in range(10):
            slot = pygame.Rect(slot_x0 + i * 92, 440, 88, 88)
            pygame.draw.rect(screen, COLOR_PANEL, slot, border_radius=8)
            pygame.draw.rect(screen, COLOR_GRID, slot, 2, border_radius=8)
            if i < len(self.slots):
                u = self.slots[i]
                # 槽位显示角色完整 Q 版形象（名字用全名，SP 形态与普通形态区分开）
                draw_unit_icon(screen, u, slot.centerx, slot.centery - 10, (40, 52))
                nm = make_font(13).render(u["name"], True, COLOR_TEXT)
                screen.blit(nm, (slot.x + 6, slot.y + 50))
        cnt = make_font(18).render(f"已选 {len(self.slots)}/10", True, COLOR_GOLD)
        screen.blit(cnt, (80, 390))
        if self.msg:
            mtxt = make_font(18).render(self.msg, True, COLOR_RED)
            screen.blit(mtxt, (SCREEN_WIDTH//2 - mtxt.get_width()//2, 520))
        self.start_btn.draw(screen)
        self.back_btn.draw(screen)

# ---------------------------------------------------------------
# 9.5 战斗界面：核心塔防场景
# ---------------------------------------------------------------
# ---------------------------------------------------------------
# 9.3.6 沙盒模式：自由放置所有我方单位与怪物
# ---------------------------------------------------------------
class SandboxScene:
    """沙盒模式：从主界面进入，可在 5×12 网格上随意放置任意我方单位
       （无需能量/冷却）和任意怪物（放下后按正常 AI 行动，可观察战斗表现）。
       操作：顶部点怪物、底部点单位选中，再点网格放置；
       空格 = 鼠标附近单位释放大招（沙盒内无冷却、无限次）；
       【休憩令】按钮 = 移除模式（点击单位/怪物可移除）；
       【暂停】【清空战场】可控制战场；怪物走到最左边界自动消失。"""
    def __init__(self, game):
        self.game = game
        self.sandbox = True                # 标记：沙盒内大招无冷却无限次（cast_ult 读取）
        self.energy = 0                    # 沙盒内的能源计数（里昂产球拾取仍生效，仅作展示）
        self.defenders = []                # 我方单位
        self.monsters = []                 # 怪物
        self.bullets = []
        self.firezones = []
        self.orbs = []
        self.fx = []                       # 飘动伤害/治疗数字
        self.ice_fx, self.spray_fx, self.burst_fx = [], [], []
        self.flash_fx = []               # 全屏闪光轰炸特效（雷纳·终末爆轰）
        self.bolt_fx, self.storm_fx = [], []
        self.water_fx, self.whirl_fx, self.sonic_fx = [], [], []
        self.helio_seal_fx = []          # 赫利俄恒光刻印光束特效
        self.rog_slash_fx = []           # 罗格斩击刀光特效（2×3横扫/三行裂斩）
        self.cross_fx = []               # 十字光标锁定特效（瓦伦丁狙杀）
        self.snipe_fx = []               # 狙击线/战术再部署特效（瓦伦丁）
        self.paused = False
        self.hoe = False                   # 移除模式（休憩令）
        self.sel_kind = "unit"             # 当前选中类型："unit" / "monster"
        self.sel_uid = UNITS[0]["uid"]
        # 上下选卡面板的横向滚动偏移（卡多放不下时用滚轮滚动选择）
        self.mon_scroll = 0
        self.unit_scroll = 0
        self.hint = "沙盒模式：点顶部选怪物 / 底部选单位，再点网格放置；空格 = 大招；滚轮可滚动选卡"
        b = make_font(18)
        self.back  = Button(1180, 8, 94, 46, "返回", self.goto_menu, b)
        self.pause = Button(1072, 8, 100, 46, "暂停", self.toggle_pause, b)
        self.speed_btn = Button(966, 8, 100, 46, "加速 ×1", self.toggle_speed, make_font(16))
        self.clear = Button(850, 8, 108, 46, "清空战场", self.clear_all, b)
        self.hoe_btn = Button(720, 8, 120, 46, "休憩令：移除", self.toggle_hoe, b)
        self.time_scale = 1                    # 当前倍速（1=正常 / 2=两倍速，update 按此循环推进）
        # 怪物面板预览实例（绘制时临时改坐标画小图）
        self.mon_previews = {u["uid"]: Monster(u["uid"], 0) for u in MONSTERS}

    def goto_menu(self): self.game.scene = "menu"
    def toggle_pause(self):
        self.paused = not self.paused
        self.pause.text = "继续" if self.paused else "暂停"
    def clear_all(self):
        self.defenders.clear(); self.monsters.clear(); self.bullets.clear()
        self.firezones.clear(); self.orbs.clear(); self.fx.clear()
        self.ice_fx.clear(); self.spray_fx.clear(); self.burst_fx.clear()
        self.bolt_fx.clear(); self.storm_fx.clear()
        self.cross_fx.clear(); self.snipe_fx.clear()
    def toggle_hoe(self):
        self.hoe = not self.hoe
        self.hoe_btn.text = "休憩令：放置" if self.hoe else "休憩令：移除"
    def toggle_speed(self):
        """切换沙盒速度：×1 ↔ ×2（与战斗场景一致，全场景同步提速）。"""
        self.time_scale = 2 if self.time_scale == 1 else 1
        self.speed_btn.text = f"加速 ×{self.time_scale}"
        self.hint = "沙盒 ×2：全场加速" if self.time_scale == 2 else "沙盒速度恢复正常 ×1"
    def set_hint(self, s): self.hint = s

    def _mon_scroll_max(self):
        """顶部怪物面板可滚动上限（面板可见宽度 704px = 8格）。"""
        return max(0, len(MONSTERS) * 88 - 704)

    def _unit_scroll_max(self):
        """底部单位面板可滚动上限（面板可见宽度 1012px = 11格）。"""
        return max(0, len(UNITS) * 92 - 1012)

    def ctx(self):
        """供实体访问的共享运行数据字典（与战斗场景结构一致）。"""
        return dict(scene=self, defenders=self.defenders, monsters=self.monsters,
                    bullets=self.bullets, orbs=self.orbs, firezones=self.firezones)

    def handle_event(self, event):
        self.back.handle_event(event)
        self.pause.handle_event(event)
        self.clear.handle_event(event)
        self.hoe_btn.handle_event(event)
        self.speed_btn.handle_event(event)
        # 数字键 1-0：选择底部单位面板当前可见的对应槽位单位（对齐战斗模式的放置逻辑）
        if event.type == pygame.KEYDOWN:
            slot = None
            if pygame.K_1 <= event.key <= pygame.K_9:
                slot = event.key - pygame.K_1
            elif event.key == pygame.K_0:
                slot = 9
            if slot is not None:
                idx = slot + self.unit_scroll // 92   # 加上面板滚动偏移
                if 0 <= idx < len(UNITS):
                    self.sel_kind = "unit"
                    self.sel_uid = UNITS[idx]["uid"]
                    self.hint = f"已选择：{UNITS[idx]['name']}（点击网格放置）"
                return
            # Backspace：直接铲除鼠标所在格的角色（与战斗一致，无需先拿起休憩令）
            if event.key == pygame.K_BACKSPACE:
                mx, my = pygame.mouse.get_pos()
                if GRID_TOP <= my < GRID_BOTTOM:
                    cx = mx // CELL_W * CELL_W + CELL_W // 2
                    cy = GRID_TOP + (my - GRID_TOP) // CELL_H * CELL_H + CELL_H // 2
                    target = next((dd for dd in self.defenders
                                   if abs(dd.x - cx) < 10 and abs(dd.y - cy) < 10), None)
                    if target is None:
                        self.hint = "该格没有单位可铲除"
                        return
                    self.defenders.remove(target)
                    self.hint = f"已铲除 {target.name}（快捷键）"
                    return
        # 空格：对鼠标附近的单位释放大招（沙盒内无冷却、不限次）；
        # 若鼠标悬停在罗格SP上则改为切换三元素形态（不消耗次数、不显示大招）
        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            mx, my = pygame.mouse.get_pos()
            for d in self.defenders:
                if abs(d.x - mx) < 42 and abs(d.y - my) < 42:
                    if getattr(d, "is_sp", False) and d.behavior == "rog":
                        d.set_rog_form(d.rog_form + 1)
                        nm = ("炽焰征伐", "霜狱禁锢", "腐毒蚀骨")[d.rog_form]
                        cc = (DAMAGE_COLOR_FIRE, DAMAGE_COLOR_ICE, DAMAGE_COLOR_POISON)[d.rog_form]
                        self.fx.append(FloatingText(d.x, d.y - 42, f"形态:{nm}", cc, 15))
                        self.hint = f"{d.name} 切换形态 → {nm}"
                    elif d.cast_ult(self.ctx()):
                        self.hint = f"{d.name} 释放大招！"
                    else:
                        self.hint = (f"{d.name} 没有大招（一次性）" if d.behavior == "fire"
                                     else "该单位大招暂不可用")
                    break
        if event.type == pygame.MOUSEWHEEL:
            # 鼠标在哪个面板上，就滚动哪个面板（滚轮向上=往前翻）
            mx, my = pygame.mouse.get_pos()
            if 6 <= my <= 56:
                self.mon_scroll = max(0, min(self.mon_scroll - event.y * 44, self._mon_scroll_max()))
            elif 540 <= my <= 636:
                self.unit_scroll = max(0, min(self.unit_scroll - event.y * 46, self._unit_scroll_max()))
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            # 顶部怪物面板（点击判断计入滚动偏移）
            if 6 <= my <= 56:
                i = int((mx - 6 + self.mon_scroll) // 88)
                if 0 <= i < len(MONSTERS):
                    self.sel_kind = "monster"
                    self.sel_uid = MONSTERS[i]["uid"]
                return
            # 底部单位面板（点击判断计入滚动偏移）
            if 540 <= my <= 636:
                i = int((mx - 6 + self.unit_scroll) // 92)
                if 0 <= i < len(UNITS):
                    self.sel_kind = "unit"
                    self.sel_uid = UNITS[i]["uid"]
                return
            # 网格：放置 / 移除
            if GRID_TOP <= my <= GRID_BOTTOM and 0 <= mx <= GRID_COLS * CELL_W:
                col = int(mx // CELL_W)
                row = int((my - GRID_TOP) // CELL_H)
                cx = col * CELL_W + CELL_W // 2
                cy = GRID_TOP + row * CELL_H + CELL_H // 2
                if self.hoe:
                    self._remove_at(cx, cy)
                else:
                    self._place(cx, cy, row)

    def _remove_at(self, cx, cy):
        """休憩令：移除最接近点击位置的单位或怪物。"""
        best, bd = None, 1e9
        for d in self.defenders:
            dist = abs(d.x - cx) + abs(d.y - cy)
            if dist < bd: bd, best = dist, d
        for m in self.monsters:
            dist = abs(m.x - cx) + abs(m.y - cy)
            if dist < bd: bd, best = dist, m
        if best is not None:
            if best in self.defenders:
                self.defenders.remove(best)
            else:
                self.monsters.remove(best)
            self.hint = "已移除该单位/怪物"

    def _place(self, cx, cy, row):
        if self.sel_kind == "monster":
            m = Monster(self.sel_uid, row)
            m.x = cx
            m.y = cy if not m.giant else 295   # 巨型怪固定中线（横跨全部行）
            self.monsters.append(m)
            self.hint = f"放置怪物：{m.name}"
            return
        d = next(u for u in UNITS if u["uid"] == self.sel_uid)
        # 第一格（最右列）禁止部署我方单位：该格是怪物出生点，留给怪物走出（怪物本身可放第一格）
        if cx // CELL_W >= GRID_COLS - 1:
            self.hint = "最右列第一格不能部署单位"
            return
        # SP 规则：必须种在对应的普通形态上（沙盒同样遵守）
        if d.get("is_sp"):
            base_uid = d["uid"].rsplit("_", 1)[0]
            exist = None
            for x in self.defenders:
                if abs(x.x - cx) < CELL_W * 0.6 and abs(x.y - cy) < CELL_H * 0.6:
                    exist = x
                    break
            if exist is None or exist.uid != base_uid:
                base_name = next(u for u in UNITS if u["uid"] == base_uid)["name"]
                self.hint = f"{d['name']} 必须放置在普通形态上（{base_name}）"
                return
            self.defenders.remove(exist)
        else:
            # 沙盒为自由测试环境：普通卡允许同格叠加部署多个（可测埃利奥特光环叠加等）
            pass
        self.defenders.append(Defender(self.sel_uid, cx, cy))
        self.hint = f"放置单位：{d['name']}"

    def update(self):
        """沙盒更新：按 time_scale 倍速循环推进（×2 时每帧跑两遍单帧逻辑，全场景同步提速）。"""
        for _ in range(self.time_scale):
            self._update_inner()
            if self.paused:
                break

    def _update_inner(self):
        """单帧沙盒逻辑（加速时被 update 循环多次调用）：单位/怪物/子弹/特效推进。"""
        if self.paused:
            return
        mouse = pygame.mouse.get_pos()
        # 帧初清零埃利奥特光环覆盖计数（支持多个埃利奥特叠加）
        for _d in self.defenders:
            _d._in_ell_rings = 0
        # 我方单位行动（攻击/产出/大招连发等）
        for d in self.defenders:
            d.update(self.ctx(), mouse)
        # 埃利奥特光环叠加汇总：按本帧覆盖光环数累加攻加
        for d in self.defenders:
            if d._in_ell_rings > 0:
                d.buff_atk = 0.5 * d._in_ell_rings
                d.buff_atk_timer = 5 * FPS
        # 怪物行动（左移/攻击单位/召唤等）
        for m in self.monsters:
            m.update(self.ctx())
        # 子弹移动与命中（与战斗场景同逻辑）
        for b in self.bullets[:]:
            b.update()
            if b.x > SCREEN_WIDTH:
                self.bullets.remove(b)
                continue
            for m in self.monsters[:]:
                hit = (m.x <= b.x <= m.x + 66) if m.giant else (abs(b.x - m.x) < (100 if getattr(b, "pierce", False) else 28) and abs(b.y - m.y) < 28)
                # 贯穿弹（琮）：已穿透过的怪物不再重复命中（避免同一目标被反复造成伤害）
                if getattr(b, "pierce", False) and m in b.pierce_hit:
                    continue
                if hit and not getattr(m, "spawn_protect", False):
                    # 贯穿弹命中后记录目标（对象引用），后续不再对该目标重复穿透
                    if getattr(b, "pierce", False):
                        b.pierce_hit.append(m)
                    # 元素状态附加与元素反应（弹丸命中触发）
                    pre_resist = m.resist_of(b.element)   # 命中前抗性快照（避免本发附加的寒冷影响本次伤害）
                    bonus, extras = apply_elemental_hit(b.element, m, b.damage, self.monsters)
                    # 统一伤害结算：弹丸携带攻击方属性快照，怪物提供防御/抗性
                    dmg, crit = DamageSystem.calc(
                        base_atk=b.damage, element=b.element,
                        defense=m.defense, resist=pre_resist,
                        atk_pct=b.attrs.get("atk_pct", 0.0), flat_atk=b.attrs.get("flat_atk", 0.0),
                        mult=b.attrs.get("mult", 1.0), pierce=b.attrs.get("pierce", 0.0),
                        dmg_inc=b.attrs.get("dmg_inc", 0.0) + bonus,
                        armor_reduce=b.attrs.get("armor_reduce", 0.0),
                        resist_reduce=b.attrs.get("resist_reduce", 0.0),
                        crit_rate=b.attrs.get("crit_rate", None),
                        crit_dmg=b.attrs.get("crit_dmg", None))
                    # 附带真实伤害（埃利奥特暴走独奏）：无视防御/抗性/暴击直接附加
                    td = b.attrs.get("true_dmg", 0)
                    if td:
                        dmg += td
                    m.take_hit(dmg, "pierce" if getattr(b, "pierce", False) else "bullet")
                    # 感电/爆炸额外伤害（雷元素反应产物）
                    for (t, ed, el, label) in extras:
                        if t.hp > 0 and t in self.monsters:
                            t.take_hit(ed, "explosive" if label == "爆炸" else "aoe")
                            self.fx.append(FloatingText(t.x, t.y - 26, f"-{ed}",
                                                        DamageSystem.text_color(el), 14))
                            if t.hp <= 0:
                                t.die(self)
                    tcol = DamageSystem.text_color(b.element, getattr(b, "epic", False), crit)
                    if getattr(b, "epic", False):
                        fy = m.y - 34 + (b.y - m.y) // 2
                        self.fx.append(FloatingText(m.x, fy, f"-{dmg}", tcol, 20 if not crit else 26))
                        self.burst_fx.append(EnergyBurstFx(b.x, b.y, 42))
                    elif getattr(b, "ult", False):
                        self.fx.append(FloatingText(m.x, m.y - 30, f"-{dmg}", tcol, 20 if not crit else 26))
                    else:
                        self.fx.append(FloatingText(m.x, m.y - 26, f"-{dmg}", tcol, 16 if not crit else 22))
                    # 白夜SP白银冰破弹：命中后对其3×3范围内其它敌人额外溅射50%冰伤
                    apply_sp_ice_splash(m, b, self.monsters, self)
                    if getattr(b, "pierce", False):
                        b.pierce_left -= 1
                        if b.pierce_left <= 0:
                            self.bullets.remove(b)
                    if m.hp <= 0:
                        m.die(self)
                    if not getattr(b, "pierce", False) and b in self.bullets:
                        self.bullets.remove(b)
                    break
        # 火区 / 能源球 / 飘字 / 各特效列表更新
        for fz in self.firezones[:]:
            if not fz.update(self.ctx()):
                self.firezones.remove(fz)
        for o in self.orbs[:]:
            if not o.update(self.ctx(), mouse):
                self.orbs.remove(o)
        for ft in self.fx[:]:
            if not ft.update():
                self.fx.remove(ft)
        for ef in self.ice_fx[:]:
            if not ef.update(): self.ice_fx.remove(ef)
        for ef in self.spray_fx[:]:
            if not ef.update(): self.spray_fx.remove(ef)
        for ef in self.burst_fx[:]:
            if not ef.update(): self.burst_fx.remove(ef)
        for ef in self.flash_fx[:]:
            if not ef.update(): self.flash_fx.remove(ef)
        for ef in self.bolt_fx[:]:
            if not ef.update(): self.bolt_fx.remove(ef)
        for ef in self.storm_fx[:]:
            if not ef.update(): self.storm_fx.remove(ef)
        for ef in self.water_fx[:]:
            if not ef.update(): self.water_fx.remove(ef)
        for ef in self.whirl_fx[:]:
            if not ef.update(): self.whirl_fx.remove(ef)
        for ef in self.sonic_fx[:]:
            if not ef.update(): self.sonic_fx.remove(ef)
        for ef in self.helio_seal_fx[:]:
            if not ef.update(): self.helio_seal_fx.remove(ef)
        for ef in self.rog_slash_fx[:]:
            if not ef.update(): self.rog_slash_fx.remove(ef)
        for ef in self.cross_fx[:]:
            if not ef.update(): self.cross_fx.remove(ef)
        for ef in self.snipe_fx[:]:
            if not ef.update(): self.snipe_fx.remove(ef)
        # 死亡实体移除；怪物走出左边界自动消失（沙盒无基地概念）。
        # 测试沙包（dummy）例外：不因 hp<=0 被移除（每5秒 update 会自动回满血），否则DPS沙包会"被打死"
        self.defenders = [d for d in self.defenders if d.hp > 0]
        self.monsters = [m for m in self.monsters if (m.hp > 0 or m.dummy) and m.x > 30]

    def draw(self, screen):
        screen.fill(COLOR_BG)
        # 网格
        for r in range(GRID_ROWS):
            for col in range(GRID_COLS):
                x, y = col * CELL_W, GRID_TOP + r * CELL_H
                pygame.draw.rect(screen, COLOR_GRID, (x, y, CELL_W, CELL_H), 1)
                if col == GRID_COLS - 1:            # 第一格（怪物出生区）不能种：画灰叉
                    draw_first_col_x(screen, x, y)
        # 实体（火区最底层，能源球在单位上层）
        for fz in self.firezones: fz.draw(screen)
        for b in self.bullets: b.draw(screen)
        for d in self.defenders: d.draw(screen)
        for o in self.orbs: o.draw(screen)
        for m in self.monsters: m.draw(screen)
        for ft in self.fx: ft.draw(screen)
        for ef in self.ice_fx: ef.draw(screen)
        for ef in self.spray_fx: ef.draw(screen)
        for ef in self.burst_fx: ef.draw(screen)
        for ef in self.bolt_fx: ef.draw(screen)
        for ef in self.storm_fx: ef.draw(screen)
        for ef in self.water_fx: ef.draw(screen)
        for ef in self.whirl_fx: ef.draw(screen)
        for ef in self.sonic_fx: ef.draw(screen)
        for ef in self.helio_seal_fx: ef.draw(screen)
        for ef in self.rog_slash_fx: ef.draw(screen)
        for ef in self.cross_fx: ef.draw(screen)
        for ef in self.snipe_fx: ef.draw(screen)
        # 鼠标悬停：显示单位名字
        mx, my = pygame.mouse.get_pos()
        for d in self.defenders:
            if abs(d.x - mx) < 42 and abs(d.y - my) < 42:
                nm = make_font(16).render(d.name, True, COLOR_WHITE)
                tag = pygame.Surface((nm.get_width() + 16, 24), pygame.SRCALPHA)
                tag.fill((15, 18, 22, 210))
                pygame.draw.rect(tag, (120, 128, 140), tag.get_rect(), 1, border_radius=4)
                tag.blit(nm, (8, 4))
                screen.blit(tag, (int(d.x) - tag.get_width() // 2, int(d.y) - 46))
        # 顶部怪物面板（选中项金色高亮；按滚动偏移裁剪，卡多时滚轮翻页）
        for i, u in enumerate(MONSTERS):
            rx = 6 + i * 88 - self.mon_scroll
            if rx + 84 < 6 or rx > 710:
                continue    # 超出可见区域的不画
            sel = self.sel_kind == "monster" and self.sel_uid == u["uid"]
            pygame.draw.rect(screen, COLOR_PANEL, (rx, 6, 84, 50), border_radius=6)
            pygame.draw.rect(screen, COLOR_GOLD if sel else COLOR_GRID, (rx, 6, 84, 50), 2, border_radius=6)
            pm = self.mon_previews[u["uid"]]
            pm.x = rx + 42       # 面板中心
            pm.y = 31
            if pm.giant:
                pm.draw(screen, mini=True)     # 迷你终结者图标（不溢出面板）
            else:
                pm.w, pm.h = 40, 26            # 缩小到面板内，仅画身体
                pm.draw(screen, mini=True)
            nm = make_font(12).render(u["name"], True, COLOR_WHITE)
            screen.blit(nm, (rx + 4, 38))
        # 底部单位面板（按滚动偏移裁剪）
        for i, u in enumerate(UNITS):
            rx = 6 + i * 92 - self.unit_scroll
            if rx + 88 < 6 or rx > 1018:
                continue    # 超出可见区域的不画
            sel = self.sel_kind == "unit" and self.sel_uid == u["uid"]
            pygame.draw.rect(screen, COLOR_PANEL, (rx, 540, 88, 92), border_radius=6)
            pygame.draw.rect(screen, COLOR_GOLD if sel else COLOR_GRID, (rx, 540, 88, 92), 2, border_radius=6)
            draw_unit_icon(screen, u, rx + 44, 556, (46, 56))
            nm = make_font(12).render(u["name"], True, COLOR_WHITE)
            screen.blit(nm, (rx + 4, 616))
        # 可滚动时的右侧指示箭头（半透明，提示可继续滚动）
        if self._mon_scroll_max() > 0:
            a = pygame.Surface((22, 44), pygame.SRCALPHA)
            pygame.draw.polygon(a, (255, 255, 255, 120), [(4, 8), (18, 22), (4, 36)])
            screen.blit(a, (690, 9))
        if self._unit_scroll_max() > 0:
            a = pygame.Surface((22, 88), pygame.SRCALPHA)
            pygame.draw.polygon(a, (255, 255, 255, 120), [(4, 20), (18, 44), (4, 68)])
            screen.blit(a, (1000, 542))
        # 按钮与提示（加速按钮：×2 激活时金色描边高亮）
        self.back.draw(screen)
        self.pause.draw(screen)
        self.clear.draw(screen)
        self.hoe_btn.draw(screen)
        self.speed_btn.draw(screen)
        if self.time_scale == 2:
            pygame.draw.rect(screen, COLOR_GOLD, self.speed_btn.rect, 3, border_radius=6)
        if self.hint:
            ht = make_font(15).render(self.hint, True, COLOR_GOLD)
            screen.blit(ht, (SCREEN_WIDTH // 2 - ht.get_width() // 2, 528))


# 无尽模式怪物池：随关卡数解锁更高级的怪物（基础怪出现权重高）
def endless_pool_for(n):
    """返回无尽模式第 n 关可出现的怪物 uid 池（重复=权重高）。"""
    pool = ["m_walker"] * 4            # 基础拾荒者权重最高
    if n >= 2: pool += ["m_child", "m_child", "m_dog", "m_dog"]
    if n >= 3: pool += ["m_shield", "m_shield"]
    if n >= 4: pool += ["m_tank", "m_tank"]
    if n >= 5: pool += ["m_sprint"]
    if n >= 6: pool += ["m_wolf", "m_raptor"]
    if n >= 7: pool += ["m_hexer", "m_spitter"]
    if n >= 8: pool += ["m_brute", "m_frost"]
    if n >= 9: pool += ["m_hulk"]
    if n >= 10: pool += ["m_king"]
    if n >= 11: pool += ["m_colossus", "m_tyrant"]
    if n >= 12: pool += ["m_queen", "m_leviathan"]
    return pool


class BattleScene:
    def __init__(self, game, dps_mode=False):
        self.game = game
        self.dps_mode = dps_mode          # DPS试炼场标记
        self.endless = game.endless_mode                  # 无尽模式标记
        self.endless_clear = False                        # 无尽模式：本关守住，等待点击下一关
        # 关卡数据：测试关走独立 TEST_LEVEL（selected_level 标记为 -1），无尽模式无固定关卡
        if self.endless:
            self.level = None
        elif game.selected_level == -1:
            self.level = TEST_LEVEL
        else:
            self.level = LEVELS[game.selected_level]
        # 战斗运行时数据（与 Defe nder 通过 ctx 字典共享）
        self.defenders = []
        self.monsters = []
        self.bullets = []
        self.orbs = []
        self.energy = (self.game.endless_energy or 200) if self.endless else self.level["start_energy"]
        self.selected_card_uid = None   # 底部槽位当前选中的卡牌
        self.card_cd = {}               # 每张卡牌的部署冷却（帧）
        # 进关初始冷却：除里昂外，所有已选卡牌开局即处于部署冷却（里昂可立即部署）
        for _u in self.game.selected_cards:
            if _u != "leon":
                _d = next((x for x in UNITS if x["uid"] == _u), None)
                if _d is None:
                    continue   # 无效/旧存档遗留的 uid 直接跳过，避免崩溃
                self.card_cd[_u] = _d["cd"] * FPS
        self.game_over = False
        self.win = False
        self.ult_charges = 5      # 每局可使用大招的次数
        self.hint = ""            # 当前操作提示（部署失败/SP升级等）
        self.hint_timer = 0       # 提示剩余帧数
        self.firezones = []       # 火区列表（伊格尼斯燃烧瓶）
        self.fx = []              # 飘动的伤害数值列表（FloatingText）
        self.ice_fx = []          # 冰雨特效列表（白夜极乐冰宴）
        self.spray_fx = []        # 药雾特效列表（茯苓急救喷雾）
        self.burst_fx = []        # 能量爆发特效列表（里昂大招）
        self.flash_fx = []        # 全屏闪光轰炸特效列表（雷纳·终末爆轰）
        self.bolt_fx = []         # 电弧特效列表（莱昂纳多链式电弧）
        self.storm_fx = []        # 雷暴领域特效列表（莱昂纳多大招）
        self.water_fx = []        # 水流横扫特效列表（卡斯珀高压水流）
        self.whirl_fx = []        # 暗潮漩涡特效列表（卡斯珀大招）
        self.sonic_fx = []        # 声波爆发特效列表（埃利奥特暴走独奏）
        self.helio_seal_fx = []   # 赫利俄恒光刻印光束特效
        self.rog_slash_fx = []    # 罗格斩击/裂斩特效（2×3横扫、元素爆点、元素龙）
        self.cross_fx = []        # 十字光标锁定特效（瓦伦丁狙杀）
        self.snipe_fx = []        # 狙击线/战术再部署特效（瓦伦丁）
        # 波次管理
        self.wave_idx = 0
        self.spawn_queue = []
        self.spawn_timer = 0
        self.wave_gap_timer = 0
        self.action_sys = ActionSystem()
        # 难度倍率：影响每波出怪量(spawn_mult)与怪物血量/护甲(hp_mult)
        cfg = DIFF_CONFIG.get(self.game.difficulty, DIFF_CONFIG["简单"])
        self.spawn_mult = cfg["spawn_mult"]
        self.hp_mult = cfg["hp_mult"]
        # 测试关（末日终结者）：出怪队列固定1只（prepare_wave 中处理）；
        # 出怪频率倍率也归1（只有1只，不影响），血量按难度翻倍照常
        if self.level and any("m_end" in w["spawn"] for w in self.level["waves"]):
            self.spawn_mult = 1
        # ---- DPS 试炼场：不开波次，改为开场放置一排测试沙包（每行1个，最后一列） ----
        self.dps_running = False      # 是否正在计时
        self.dps_frames = 0           # 已计时帧数
        self.total_damage = 0         # 累计总伤害
        self.total_waves = 0          # 总波数（init_waves 会重设；DPS试炼场保持0，跳过胜负判定）
        # ---- 关卡规则（创意关卡：沙尘暴/铁雨空降/辐射潮汐/精英血脉）----
        self.rules = self.level.get("rules", []) if self.level else []
        self.rule_desc = (self.level.get("rule_desc", "") if self.level
                          else f"无尽模式 第{self.game.endless_stage}关：怪物逐关递增")
        self.rule_timer = 0           # 规则计时（铁雨空降/辐射潮汐共用）
        if self.rules and not self.dps_mode:
            self.set_hint(f"本关规则：{self.rule_desc}")
        if self.endless:
            # 无尽模式：恢复上一关保留的单位部署与能量（跨关保留布局）
            if self.game.endless_keep_units:
                for uid, cx, cy, ratio, ult_cd, rog_form, eternal in self.game.endless_keep_units:
                    dd = Defender(uid, cx, cy)
                    dd.hp = max(1, int(dd.maxhp * ratio))
                    dd.ult_cd = ult_cd
                    if getattr(dd, "is_sp", False) and dd.behavior == "rog":
                        dd.set_rog_form(rog_form)      # 恢复烬SP切换的形态
                    if eternal:
                        # 恢复恒光刻印（赫利俄大招永久增益跨关保留）
                        dd.eternal_seal = True
                        dd.atk_iv = max(0.2, dd.atk_iv / 2)
                        dd.resist_reduce += 0.5
                    self.defenders.append(dd)
                self.set_hint(f"已保留上一关 {len(self.game.endless_keep_units)} 个单位的部署")
            elif self.game.endless_stage == 1:
                self.set_hint("无尽模式：守住尽可能多的关卡，每关怪物会越来越多")
            self.total_waves = 4          # 无尽每关固定4波（波次翻倍）
            self.wave_idx = 0
            self.wave_gap = 2 * FPS       # 波间停顿2秒
            self.next_btn = Button(SCREEN_WIDTH//2 - 130, SCREEN_HEIGHT//2 + 70, 260, 50,
                                   "下一关：重新选卡", self.goto_next_endless, make_font(20))
            self.prepare_endless_wave()
        elif self.dps_mode:
            self.energy = 9999
            self.ult_charges = 9999
            for r in range(GRID_ROWS):
                m = Monster("m_dummy", r)
                m.x = (GRID_COLS - 1) * CELL_W + CELL_W // 2
                m.y = GRID_TOP + r * CELL_H + CELL_H // 2
                self.monsters.append(m)
        else:
            self.init_waves()
        self.back = Button(30, 12, 120, 36, "退出战斗", self.goto_menu, make_font(18))
        # ---- 休憩令（铲子）：点击后进入铲除模式，可铲除场上单位 ----
        self.hoe_mode = False                                # 休憩令是否已拿起
        self.hoe_btn = Button(SCREEN_WIDTH - 148, 12, 136, 36, "休憩令（铲除）", self.toggle_hoe, make_font(15))
        # ---- 加速功能：×1/×2 切换，全场景逻辑速度翻倍（DPS试炼场不提供，保持计时语义纯净） ----
        self.time_scale = 1                    # 当前倍速（1=正常 / 2=两倍速，update 按此循环推进）
        if not self.dps_mode:
            self.speed_btn = Button(SCREEN_WIDTH - 296, 12, 136, 36, "加速 ×1", self.toggle_speed, make_font(16))
        # ---- DPS 试炼场控制按钮：开始计时 / 重置 ----
        if self.dps_mode:
            self.dps_btn = Button(846, 12, 110, 36, "开始计时", self.toggle_dps, make_font(18))
            self.dps_reset = Button(966, 12, 96, 36, "重置", self.reset_dps, make_font(18))
        # 进入战斗时先提示一次大招操作
        self.set_hint("操作：鼠标对准单位，按【空格】释放大招")

    def goto_menu(self):
        """返回主菜单；无尽模式下先把当前阵容与关卡存档落盘（关闭程序后仍可恢复），再重置内存。"""
        if self.endless:
            self.save_endless()                   # 把当前单位部署/形态/能量写回内存
            self.game.save_endless_snapshot()     # 落盘持久化
            self.game.reset_endless()             # 清空内存状态（下次进入再从存档恢复）
        self.game.scene = "menu"

    def prepare_endless_wave(self):
        """无尽模式：生成当前关卡的一波怪物（数量随关卡递增，种类随关卡解锁）。
           每一小波怪物一次性整扎堆生成（不再逐只间隔出现）；生成在最右列，带生成保护
           （第一格不被打，走到第二格才被攻击）。"""
        N = self.game.endless_stage
        wave_no = self.wave_idx + 1                       # 第1波 / 第2波
        count = (1 + N) + (wave_no - 1) * 2               # 第1波 1+N 只，第2波 3+N 只
        pool = endless_pool_for(N)
        for _ in range(count):
            m = Monster(random.choice(pool), self.get_row())
            # 无尽怪物血量随关卡递增：第 n 关血量提升最初始血量的 (n-1)%，即 ×(1+(n-1)/100)
            stage_mult = 1.0 + (N - 1) / 100.0
            m.hp_mult = stage_mult
            m.maxhp = int(m.maxhp * stage_mult)
            m.hp = m.maxhp                                   # 满血出生
            m.spawn_protect = True                        # 生成保护：最后一格不被打，走到第二格才被攻击
            self.monsters.append(m)                       # 整波一次性扎堆出场
        self.wave_idx += 1

    def save_endless(self):
        """无尽模式：把当前单位部署、能量、形态与恒光刻印存到 Game，供下一关恢复。"""
        self.game.endless_keep_units = []
        for d in self.defenders:
            self.game.endless_keep_units.append((d.uid, d.x, d.y, d.hp / d.maxhp, d.ult_cd,
                                                 getattr(d, "rog_form", 0),
                                                 getattr(d, "eternal_seal", False)))
        self.game.endless_energy = self.energy

    def goto_next_endless(self):
        """无尽模式：守住本关 → 保存部署 → 进入下一关选卡（同时落盘存档）。"""
        self.save_endless()
        self.game.endless_stage += 1
        self.game.save_endless_snapshot()   # 转关后立即落盘，关闭程序也不丢失
        self.game.scene = "card"

    def set_hint(self, msg):
        """显示一条短暂的操作提示（部署失败 / SP 升级等），约2秒后消失。"""
        self.hint = msg
        self.hint_timer = 2 * FPS

    def toggle_dps(self):
        """DPS 试炼场：开始/暂停计时（开始瞬间清零时间与总伤害）。"""
        self.dps_running = not self.dps_running
        if self.dps_running:
            self.dps_frames = 0
            self.total_damage = 0
            self.dps_btn.text = "暂停计时"
        else:
            self.dps_btn.text = "开始计时"

    def reset_dps(self):
        """DPS 试炼场：停止计时并清零数据。"""
        self.dps_running = False
        self.dps_frames = 0
        self.total_damage = 0
        self.dps_btn.text = "开始计时"

    def toggle_hoe(self):
        """切换休憩令（铲子）模式：拿起后点击场上单位即可铲除，再点按钮收回。"""
        self.hoe_mode = not self.hoe_mode
        if self.hoe_mode:
            self.selected_card_uid = None          # 收起选卡，避免铲除时误放单位
            self.set_hint("休憩令已拿起：点击战场中的单位即可铲除；再点【休憩令】收回")
        else:
            self.set_hint("休憩令已收回")

    def slot_uid(self, slot):
        """返回卡槽第 slot 张（0 起）卡牌对应的 uid。
           普通战斗：出战卡 selected_cards[slot]；DPS/测试模式：全部单位 UNITS[slot]。
           槽位不足返回 None。数字键快捷键与点击共用此索引映射。"""
        if self.dps_mode:
            return UNITS[slot]["uid"] if 0 <= slot < len(UNITS) else None
        if 0 <= slot < len(self.game.selected_cards):
            return self.game.selected_cards[slot]["uid"]
        return None

    def place_card(self, cx, cy, uid):
        """把指定 uid 的卡牌放置到网格格心(cx,cy)。鼠标点击与数字键快捷键共用此逻辑。
           内部完成能量/冷却校验、SP 需种在普通形态上原地替换、普通卡只放空格等规则。
           返回 True=放置成功；False=失败（已给出具体提示）。"""
        # 第一格（最右列）禁止部署单位：该格是怪物出生点，留给怪物走出，玩家不可占用
        if cx // CELL_W >= GRID_COLS - 1:
            self.set_hint("最右列第一格不能部署单位")
            return False
        d = next(u for u in UNITS if u["uid"] == uid)
        existing = next((dd for dd in self.defenders
                         if abs(dd.x - cx) < 10 and abs(dd.y - cy) < 10), None)
        if self.energy < d["cost"]:
            self.set_hint("能量不足！")
            return False
        if self.card_cd.get(uid, 0) > 0:
            self.set_hint("该卡牌还在冷却中")
            return False
        if d.get("is_sp"):
            # SP 卡：必须种植在对应的普通形态上（原地替换升级）
            if existing is None:
                base = next(x["name"] for x in UNITS if x["uid"] == d.get("sp_of"))
                self.set_hint(f"SP 需要先种植普通形态【{base}】再升级")
                return False
            if existing.uid != d.get("sp_of"):
                self.set_hint("只能替换对应的普通形态，不能放在其他单位上")
                return False
            old_rate = existing.hp / existing.maxhp
            self.defenders.remove(existing)
            sp = Defender(uid, cx, cy)
            sp.hp = max(1, int(sp.maxhp * old_rate))
            self.defenders.append(sp)
            self.energy -= d["cost"]
            self.card_cd[uid] = d["cd"] * FPS
            self.set_hint(f"升级为 {d['name']}！")
        else:
            # 普通卡：默认只能放空格；测试模式（测试开关/DPS试炼场）允许同格叠加部署多个
            if existing is not None and not (self.game.cheat or self.dps_mode):
                self.set_hint("该格已被占用，不能重复放置")
                return False
            self.defenders.append(Defender(uid, cx, cy))
            self.energy -= d["cost"]
            self.card_cd[uid] = d["cd"] * FPS
        return True

    def toggle_speed(self):
        """切换战斗速度：×1 ↔ ×2。
           实现方式：update() 按 time_scale 循环推进单帧逻辑，因此怪物移动/攻击、
           出怪频率、关卡规则、弹丸、特效、状态计时等全部同步翻倍。"""
        self.time_scale = 2 if self.time_scale == 1 else 1
        self.speed_btn.text = f"加速 ×{self.time_scale}"
        self.set_hint("战斗速度 ×2：全场单位与怪物加速行动" if self.time_scale == 2
                      else "战斗速度恢复正常 ×1")

    def try_hoe(self, mx, my):
        """休憩令模式下点击：铲除鼠标所指格子上的单位（不返还能量）。"""
        if not (GRID_TOP <= my < GRID_BOTTOM):
            self.set_hint("休憩令：请点击战场格子里的单位")
            return
        cx = mx // CELL_W * CELL_W + CELL_W // 2
        cy = GRID_TOP + (my - GRID_TOP) // CELL_H * CELL_H + CELL_H // 2
        target = next((dd for dd in self.defenders
                       if abs(dd.x - cx) < 10 and abs(dd.y - cy) < 10), None)
        if target is None:
            self.set_hint("休憩令：这个格子没有单位")
            return
        self.defenders.remove(target)
        self.set_hint(f"已铲除 {target.name}（休憩令）")

    def init_waves(self):
        """把当前关卡的所有波次压入生成队列（记录当前波/整体进度）。
           普通关波次翻倍：测试关（末日终结者固定1只）保持不变。"""
        is_test = any("m_end" in w["spawn"] for w in self.level["waves"])
        self._waves = self.level["waves"] if is_test else self.level["waves"] * 2
        self.total_waves = len(self._waves)
        self.wave_idx = 0
        self.prepare_wave()

    def prepare_wave(self):
        if self.wave_idx < self.total_waves:
            wave = self._waves[self.wave_idx]
            # 出怪规则：每波基础怪物 = 波次列表 ×3（简单模式也有群怪，方便观察溅射/范围特效）；
            # 难度倍率不再复制总量，只加快出怪频率（见 spawn_timer 间隔除以 spawn_mult）
            if any("m_end" in w["spawn"] for w in self.level["waves"]):
                self.spawn_queue = list(wave["spawn"])     # 测试关：始终固定1只末日终结者
            else:
                self.spawn_queue = list(wave["spawn"]) * 3
            self.wave_gap = wave["wave_gap"]
            self.spawn_timer = 10 * FPS      # 每波第一只：开局10秒后出现
            self.wave_idx += 1

    def get_row(self):
        return random.randint(0, GRID_ROWS - 1)

    def handle_event(self, event):
        self.back.handle_event(event)
        if not self.dps_mode:
            self.speed_btn.handle_event(event)
        if self.endless and self.endless_clear:
            self.next_btn.handle_event(event)
        if self.dps_mode:
            self.dps_btn.handle_event(event)
            self.dps_reset.handle_event(event)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not self.game_over:
            mx, my = event.pos
            # 点击休憩令按钮 -> 切换铲除模式
            if self.hoe_btn.rect.collidepoint(mx, my):
                self.toggle_hoe()
                return
            # 休憩令模式：点击铲除单位（不再选卡 / 部署）
            if self.hoe_mode:
                self.try_hoe(mx, my)
                return
            # 点击底部卡牌槽位 -> 选中（槽位区整体居中）
            if self.dps_mode:
                # DPS试炼场：底部卡槽为全部单位，槽宽自适应，无冷却限制
                units_all = UNITS
                sw = (SCREEN_WIDTH - 100) // len(units_all)
                sx0 = (SCREEN_WIDTH - len(units_all) * sw) // 2
                if my >= SCREEN_HEIGHT - 100:
                    slot = (mx - sx0) // sw
                    if 0 <= slot < len(units_all):
                        self.selected_card_uid = units_all[slot]["uid"]
                    return
            slot_x0 = (SCREEN_WIDTH - 920) // 2
            slot = (mx - slot_x0) // 92
            if my >= SCREEN_HEIGHT - 100 and 0 <= slot < 10:
                if slot < len(self.game.selected_cards):
                    uid = self.game.selected_cards[slot]["uid"]
                    # 若冷却中则不能选
                    if self.card_cd.get(uid, 0) <= 0:
                        self.selected_card_uid = uid
                return
            # 点击网格 -> 放置选中的卡牌（复用 place_card：能量/冷却/SP替换/占用校验）
            if self.selected_card_uid and GRID_TOP <= my < GRID_BOTTOM:
                cx = mx // CELL_W * CELL_W + CELL_W // 2
                cy = GRID_TOP + (my - GRID_TOP) // CELL_H * CELL_H + CELL_H // 2
                self.place_card(cx, cy, self.selected_card_uid)
                return
        # 数字键 1-0 快捷键：鼠标移到网格格子上时，直接放置卡槽第 1~10 张对应的角色
        # （槽位不足或格内已有单位/冷却/能量不足时给出提示，不静默；休憩令模式下禁用防误放）
        if event.type == pygame.KEYDOWN and not self.game_over and not self.hoe_mode:
            slot = None
            if pygame.K_1 <= event.key <= pygame.K_9:
                slot = event.key - pygame.K_1
            elif event.key == pygame.K_0:
                slot = 9
            if slot is not None:
                mx, my = pygame.mouse.get_pos()
                if GRID_TOP <= my < GRID_BOTTOM:
                    uid = self.slot_uid(slot)
                    if uid is None:
                        self.set_hint(f"卡槽{slot + 1}没有出战卡")
                        return
                    cx = mx // CELL_W * CELL_W + CELL_W // 2
                    cy = GRID_TOP + (my - GRID_TOP) // CELL_H * CELL_H + CELL_H // 2
                    self.selected_card_uid = uid
                    self.place_card(cx, cy, uid)
                return
        # Backspace 快捷键：鼠标移到网格格子上时，直接铲除该格的角色（无需先拿起休憩令）
        if event.type == pygame.KEYDOWN and event.key == pygame.K_BACKSPACE and not self.game_over:
            mx, my = pygame.mouse.get_pos()
            if GRID_TOP <= my < GRID_BOTTOM:
                cx = mx // CELL_W * CELL_W + CELL_W // 2
                cy = GRID_TOP + (my - GRID_TOP) // CELL_H * CELL_H + CELL_H // 2
                target = next((dd for dd in self.defenders
                               if abs(dd.x - cx) < 10 and abs(dd.y - cy) < 10), None)
                if target is None:
                    self.set_hint("该格没有单位可铲除")
                    return
                self.defenders.remove(target)
                self.set_hint(f"已铲除 {target.name}（快捷键）")
                return
        # 空格：对鼠标附近的单位释放大招（每局共5次机会，测试模式不限）；
        # 若鼠标悬停在罗格SP上则改为切换三元素形态（不消耗次数、不显示大招）
        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE and not self.game_over:
            if self.hoe_mode:
                self.set_hint("休憩令模式中：先点【休憩令】收回，再释放大招")
                return
            mx, my = pygame.mouse.get_pos()
            target = None
            for d in self.defenders:
                if abs(d.x - mx) < 42 and abs(d.y - my) < 42:
                    target = d
                    break
            if target is None:
                self.set_hint("把鼠标移到单位上，再按空格释放大招")
                return
            if getattr(target, "is_sp", False) and target.behavior == "rog":
                # 罗格SP：按空格切换形态（不消耗大招次数、不显示释放大招，只飘形态文字）
                target.set_rog_form(target.rog_form + 1)
                nm = ("炽焰征伐", "霜狱禁锢", "腐毒蚀骨")[target.rog_form]
                cc = (DAMAGE_COLOR_FIRE, DAMAGE_COLOR_ICE, DAMAGE_COLOR_POISON)[target.rog_form]
                self.fx.append(FloatingText(target.x, target.y - 42, f"形态:{nm}", cc, 15))
                self.set_hint(f"{target.name} 切换形态 → {nm}")
                return
            if not self.game.cheat and not self.dps_mode and self.ult_charges <= 0:
                self.set_hint("本局大招次数已用完（共5次）")
                return
            if target.cast_ult(self.ctx()):
                if not self.game.cheat and not self.dps_mode:
                    self.ult_charges -= 1
                self.set_hint(f"{target.name} 释放大招！剩余 {self.ult_charges} 次")
            else:
                if target.behavior == "fire":
                    self.set_hint(f"{target.name} 没有大招")
                else:
                    self.set_hint(f"{target.name} 的大招还在冷却中")

    def ctx(self):
        """供实体访问的共享运行数据字典（scene 引用用于改能量/胜负）。"""
        return dict(scene=self, defenders=self.defenders, monsters=self.monsters,
                    bullets=self.bullets, orbs=self.orbs, firezones=self.firezones)

    def update(self):
        """战斗场景更新：按 time_scale 倍速循环推进（×2 时每帧跑两遍单帧逻辑，
           怪物移动/攻击/出怪/规则/特效等全场景同步提速；game_over 后停止推进）。"""
        for _ in range(self.time_scale):
            self._update_inner()
            if self.game_over:
                break

    def _update_inner(self):
        """单帧战斗逻辑（加速时被 update 循环多次调用）：能量/波次/行动/特效/胜负判定。"""
        if self.game_over or self.endless_clear:
            return
        mouse = pygame.mouse.get_pos()
        # 测试模式 / DPS试炼场：能量恒为9999 + 取消种植冷却
        if self.game.cheat or self.dps_mode:
            self.energy = 9999
            for k in list(self.card_cd.keys()):
                self.card_cd[k] = 0
        # DPS 试炼场：计时 + 累计沙包受到的伤害（每帧清零，死亡复活不影响累计）
        if self.dps_mode:
            if self.dps_running:
                self.dps_frames += 1
            for m in self.monsters:
                self.total_damage += m.dmg_received
                m.dmg_received = 0
        # 关卡规则（非DPS试炼场）：铁雨空降 / 辐射潮汐 定时触发
        if self.rules and not self.dps_mode:
            self.rule_timer += 1
            if "铁雨空降" in self.rules and self.rule_timer % (15 * FPS) == 0:
                for _ in range(2):
                    r = self.get_row()
                    m = Monster("m_dog", r)
                    m.hp_mult = self.hp_mult
                    if self.hp_mult != 1.0:
                        m.maxhp = int(m.maxhp * self.hp_mult)
                        m.hp = m.maxhp
                    self.monsters.append(m)
                self.fx.append(FloatingText(SCREEN_WIDTH // 2, 90, "铁雨空降！变异犬来袭", (170, 170, 180), 16))
            if "辐射潮汐" in self.rules and self.rule_timer % (20 * FPS) == 0:
                for m in self.monsters:
                    m.hp = min(m.maxhp, m.hp + int(m.maxhp * 0.05))
                self.fx.append(FloatingText(SCREEN_WIDTH // 2, 90, "辐射潮汐：怪物恢复生命", (120, 200, 120), 16))
        # 能量不再每秒自动增长：必须靠里昂产出能源球并用鼠标拾取
        # （里昂大招也会直接产出能源；能源球价值按难度在 Defender 产球时调整）

        # 操作提示倒计时
        if self.hint_timer > 0:
            self.hint_timer -= 1
            if self.hint_timer <= 0:
                self.hint = ""

        # 卡牌部署冷却
        for k in list(self.card_cd.keys()):
            if self.card_cd[k] > 0:
                self.card_cd[k] -= 1

        # 波次生成怪物
        if self.endless:
            # 无尽模式：每一小波怪物整扎堆一次性生成；该波清空后间隔一下再开下一波
            if self.wave_idx < self.total_waves:
                if not self.monsters:
                    if self.wave_gap_timer <= 0:
                        self.prepare_endless_wave()          # 整波扎堆生成
                        self.wave_gap_timer = self.wave_gap
                    else:
                        self.wave_gap_timer -= 1
                else:
                    self.wave_gap_timer = self.wave_gap      # 场上仍有怪，保持波间待命
        elif self.wave_idx > 0 or self.spawn_queue or self.wave_gap_timer > 0:
            if self.spawn_queue:
                self.spawn_timer -= 1
                if self.spawn_timer <= 0:
                    uid = self.spawn_queue.pop(0)
                    m = Monster(uid, self.get_row())
                    m.hp_mult = self.hp_mult
                    if m.hp_mult != 1.0:
                        # 普通关卡：血量/护甲按难度倍率放大（简单1/普通2/困难2）
                        m.maxhp = int(m.maxhp * m.hp_mult)
                        m.hp = m.maxhp
                        m.armor = int(m.armor * m.hp_mult)
                        m.armor_max = m.armor
                    # 关卡规则倍率：沙尘暴（移速+15%）/ 精英血脉（血量×1.5、移速×0.9）
                    if "沙尘暴" in self.rules:
                        m.spd_mult = 1.15
                    if "精英血脉" in self.rules:
                        m.maxhp = int(m.maxhp * 1.5)
                        m.hp = m.maxhp
                        m.armor = int(m.armor * 1.5)
                        m.armor_max = m.armor
                        m.spd_mult *= 0.9
                    m.spawn_protect = True                    # 生成保护：最后一格不被打，走到第二格才被攻击
                    self.monsters.append(m)
                    # 之后每3~10秒随机出一只（基础频率）；难度按 spawn_mult 缩短间隔：
                    # 简单×1 3~10秒 / 普通×2 1.5~5秒 / 困难×5 0.6~2秒（单位时间出怪量翻倍/5倍）
                    iv = max(1, int(3 * FPS / self.spawn_mult))
                    hi = max(iv + 1, int(10 * FPS / self.spawn_mult))
                    self.spawn_timer = random.randint(iv, hi)
            else:
                # 当前波出完，等待波间隔后开下一波
                if self.wave_gap_timer <= 0 and self.wave_idx < self.total_waves:
                    self.prepare_wave()
                    self.wave_gap_timer = self.wave_gap
                elif self.wave_gap_timer > 0:
                    self.wave_gap_timer -= 1

        # 行动顺序系统：推进所有实体行动
        entities = list(self.defenders) + list(self.monsters)
        self.action_sys.tick(entities, None, mouse)
        # 帧初清零埃利奥特光环覆盖计数（每帧重算，支持多个埃利奥特叠加）
        for _d in self.defenders:
            _d._in_ell_rings = 0
        # 我方单位更新（产出/攻击/冷却）
        for d in self.defenders[:]:
            d.update(self.ctx(), mouse)
            if d.hp <= 0:
                self.defenders.remove(d)
        # 埃利奥特光环叠加汇总：按本帧覆盖光环数累加攻加（每个+50%），离开光环由 timer 递减5秒
        for d in self.defenders:
            if d._in_ell_rings > 0:
                d.buff_atk = 0.5 * d._in_ell_rings
                d.buff_atk_timer = 5 * FPS
        # 怪物更新（移动/啃咬）
        for m in self.monsters[:]:
            m.update(self.ctx())
        # 统一清理死亡怪物（火区/灼烧/近战等造成的死亡）；
        # DPS沙包不死亡（die 里原地复活），其余正常移除
        for m in self.monsters[:]:
            if m.hp <= 0:
                if m.dummy:
                    m.die(self)
                else:
                    self.monsters.remove(m)
        # 火区更新（伊格尼斯燃烧瓶）
        for fz in self.firezones[:]:
            if not fz.update(self.ctx()):
                self.firezones.remove(fz)
        # 子弹移动与命中
        for b in self.bullets[:]:
            b.update()
            if b.x > SCREEN_WIDTH:
                self.bullets.remove(b); continue
            for m in self.monsters[:]:
                # 巨型怪：命中判定看身体范围（66宽），且任意行的子弹都能打到它
                hit = (m.x <= b.x <= m.x + 66) if m.giant else (abs(b.x - m.x) < (100 if getattr(b, "pierce", False) else 28) and abs(b.y - m.y) < 28)
                # 贯穿弹（琮）：已穿透过的怪物不再重复命中（避免同一目标被反复造成伤害）
                if getattr(b, "pierce", False) and m in b.pierce_hit:
                    continue
                if hit and not getattr(m, "spawn_protect", False):
                    # 贯穿弹命中后记录目标（对象引用），后续不再对该目标重复穿透
                    if getattr(b, "pierce", False):
                        b.pierce_hit.append(m)
                    # 元素状态附加与元素反应（弹丸命中触发）
                    pre_resist = m.resist_of(b.element)   # 命中前抗性快照（避免本发附加的寒冷影响本次伤害）
                    bonus, extras = apply_elemental_hit(b.element, m, b.damage, self.monsters)
                    # 统一伤害结算：弹丸携带攻击方属性快照，怪物提供防御/抗性
                    dmg, crit = DamageSystem.calc(
                        base_atk=b.damage, element=b.element,
                        defense=m.defense, resist=pre_resist,
                        atk_pct=b.attrs.get("atk_pct", 0.0), flat_atk=b.attrs.get("flat_atk", 0.0),
                        mult=b.attrs.get("mult", 1.0), pierce=b.attrs.get("pierce", 0.0),
                        dmg_inc=b.attrs.get("dmg_inc", 0.0) + bonus,
                        armor_reduce=b.attrs.get("armor_reduce", 0.0),
                        resist_reduce=b.attrs.get("resist_reduce", 0.0),
                        crit_rate=b.attrs.get("crit_rate", None),
                        crit_dmg=b.attrs.get("crit_dmg", None))
                    # 附带真实伤害（埃利奥特暴走独奏）：无视防御/抗性/暴击直接附加
                    td = b.attrs.get("true_dmg", 0)
                    if td:
                        dmg += td
                    m.take_hit(dmg, "pierce" if getattr(b, "pierce", False) else "bullet")
                    # 感电/爆炸额外伤害（雷元素反应产物）
                    for (t, ed, el, label) in extras:
                        if t.hp > 0 and t in self.monsters:
                            t.take_hit(ed, "explosive" if label == "爆炸" else "aoe")
                            self.fx.append(FloatingText(t.x, t.y - 26, f"-{ed}",
                                                        DamageSystem.text_color(el), 14))
                            if t.hp <= 0:
                                t.die(self)
                    tcol = DamageSystem.text_color(b.element, getattr(b, "epic", False), crit)
                    if getattr(b, "epic", False):
                        # SP大招弹命中：橙色/暴击金色大号伤害数字 + 金色爆闪特效
                        # （伤害数字按弹的垂直偏移错开，5枚弹的伤害都能看清）
                        fy = m.y - 34 + (b.y - m.y) // 2
                        self.fx.append(FloatingText(m.x, fy, f"-{dmg}", tcol, 20 if not crit else 26))
                        self.burst_fx.append(EnergyBurstFx(b.x, b.y, 42))
                    elif getattr(b, "ult", False):
                        # 大招弹命中：大号伤害数字
                        self.fx.append(FloatingText(m.x, m.y - 30, f"-{dmg}", tcol, 20 if not crit else 26))
                    else:
                        # 普通子弹：按元素配色（冰弹冰蓝/物理灰），暴击统一金色
                        self.fx.append(FloatingText(m.x, m.y - 26, f"-{dmg}", tcol, 16 if not crit else 22))
                    # 白夜SP白银冰破弹：命中后对其3×3范围内其它敌人额外溅射50%冰伤
                    apply_sp_ice_splash(m, b, self.monsters, self)
                    # 贯穿弹（琮）：命中后不消失，继续向前穿透下一个敌人（最多 pierce_max 个）
                    if getattr(b, "pierce", False):
                        b.pierce_left -= 1
                        if b.pierce_left <= 0:
                            self.bullets.remove(b)
                        break    # 同一帧只穿一个敌人，下一帧继续前进再穿下一个
                    self.bullets.remove(b)
                    break
                    if m.hp <= 0:
                        m.die(self)
                    break
        # 能源球拾取
        for o in self.orbs[:]:
            if not o.update(self.ctx(), mouse):
                self.orbs.remove(o)
        # 飘动伤害数值更新（上飘 + 淡出）
        for ft in self.fx[:]:
            if not ft.update():
                self.fx.remove(ft)
        # 冰雨特效（极乐冰宴）更新
        for ef in self.ice_fx[:]:
            if not ef.update():
                self.ice_fx.remove(ef)
        # 药雾特效（急救喷雾）更新
        for ef in self.spray_fx[:]:
            if not ef.update():
                self.spray_fx.remove(ef)
        # 能量爆发特效（里昂大招）更新
        for ef in self.burst_fx[:]:
            if not ef.update():
                self.burst_fx.remove(ef)
        # 全屏闪光轰炸特效（雷纳·终末爆轰）更新
        for ef in self.flash_fx[:]:
            if not ef.update():
                self.flash_fx.remove(ef)
        # 电弧特效（莱昂纳多链式电弧）更新
        for ef in self.bolt_fx[:]:
            if not ef.update():
                self.bolt_fx.remove(ef)
        # 雷暴领域特效（莱昂纳多大招）更新
        for ef in self.storm_fx[:]:
            if not ef.update():
                self.storm_fx.remove(ef)
        # 水流横扫特效（卡斯珀普攻）更新
        for ef in self.water_fx[:]:
            if not ef.update():
                self.water_fx.remove(ef)
        # 暗潮漩涡特效（卡斯珀大招）更新
        for ef in self.whirl_fx[:]:
            if not ef.update():
                self.whirl_fx.remove(ef)
        # 声波爆发特效（埃利奥特大招）更新
        for ef in self.sonic_fx[:]:
            if not ef.update():
                self.sonic_fx.remove(ef)
        # 恒光刻印光束特效（赫利俄大招）更新
        for ef in self.helio_seal_fx[:]:
            if not ef.update():
                self.helio_seal_fx.remove(ef)
        # 罗格斩击刀光特效更新
        for ef in self.rog_slash_fx[:]:
            if not ef.update():
                self.rog_slash_fx.remove(ef)
        # 十字光标/狙击线特效（瓦伦丁）更新
        for ef in self.cross_fx[:]:
            if not ef.update():
                self.cross_fx.remove(ef)
        for ef in self.snipe_fx[:]:
            if not ef.update():
                self.snipe_fx.remove(ef)

        # 胜负判定
        if self.game_over:
            self.win = False
        elif self.wave_idx >= self.total_waves and not self.spawn_queue and not self.monsters:
            if self.endless:
                self.endless_clear = True     # 无尽模式：本关守住，等待玩家点【下一关】
            else:
                self.game_over = True
                self.win = True

    def draw(self, screen):
        screen.fill(COLOR_BG)
        # 网格
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                x, y = c * CELL_W, GRID_TOP + r * CELL_H
                pygame.draw.rect(screen, COLOR_GRID, (x, y, CELL_W, CELL_H), 1)
                if c == GRID_COLS - 1:              # 第一格（怪物出生区）不能种：画灰叉
                    draw_first_col_x(screen, x, y)
        # 实体（火区在最底层；能源球在单位上层，保证里昂产出的能量可见可拾取）
        for fz in self.firezones: fz.draw(screen)
        for b in self.bullets: b.draw(screen)
        for d in self.defenders: d.draw(screen)
        for o in self.orbs: o.draw(screen)
        for m in self.monsters: m.draw(screen)
        # 飘动的伤害数值（最上层）
        for ft in self.fx: ft.draw(screen)
        # 冰雨特效（极乐冰宴）绘制
        for ef in self.ice_fx: ef.draw(screen)
        # 药雾特效（急救喷雾）绘制
        for ef in self.spray_fx: ef.draw(screen)
        # 能量爆发特效（里昂大招）绘制
        for ef in self.burst_fx: ef.draw(screen)
        # 电弧特效（莱昂纳多链式电弧）绘制
        for ef in self.bolt_fx: ef.draw(screen)
        # 雷暴领域特效（莱昂纳多大招）绘制
        for ef in self.storm_fx: ef.draw(screen)
        # 水流横扫特效（卡斯珀普攻）绘制
        for ef in self.water_fx: ef.draw(screen)
        # 暗潮漩涡特效（卡斯珀大招）绘制
        for ef in self.whirl_fx: ef.draw(screen)
        # 声波爆发特效（埃利奥特大招）绘制
        for ef in self.sonic_fx: ef.draw(screen)
        # 恒光刻印光束特效（赫利俄大招）绘制
        for ef in self.helio_seal_fx: ef.draw(screen)
        # 罗格斩击刀光特效绘制
        for ef in self.rog_slash_fx: ef.draw(screen)
        # 十字光标/狙击线特效（瓦伦丁）绘制
        for ef in self.cross_fx: ef.draw(screen)
        for ef in self.snipe_fx: ef.draw(screen)
        # 全屏闪光轰炸特效（雷纳·终末爆轰）——最后绘制，覆盖全场形成爆炸闪光
        for ef in self.flash_fx: ef.draw(screen)
        # 鼠标悬停：显示单位名字 + 当前获得的增益/形态标签（多行，与怪物悬停共用面板绘制）
        mx, my = pygame.mouse.get_pos()
        for d in self.defenders:
            if abs(d.x - mx) < 42 and abs(d.y - my) < 42:
                # 增益/形态明细（多行小标签）
                gains = []
                if getattr(d, "eternal_seal", False):
                    gains.append("攻速+100%")
                if d.buff_atk > 0:
                    gains.append(f"攻击+{int(d.buff_atk * 100)}%")
                if d.buff_atk_ult > 0 and d.buff_atk_ult_timer > 0:
                    gains.append(f"大招攻击+{int(d.buff_atk_ult * 100)}%")
                if getattr(d, "buff_dmg_inc", 0) > 0:
                    gains.append(f"增伤+{int(d.buff_dmg_inc * 100)}%")
                if d.true_dmg_left > 0:
                    gains.append(f"附伤{int(getattr(d, 'true_dmg_val', 20))}×{d.true_dmg_left}")
                if d.buff_crit_rate > 0 or d.buff_crit_dmg > 0:
                    parts = []
                    if d.buff_crit_rate > 0:
                        parts.append(f"暴击率+{int(d.buff_crit_rate * 100)}%")
                    if d.buff_crit_dmg > 0:
                        parts.append(f"爆伤+{int(d.buff_crit_dmg * 100)}%")
                    gains.append("/".join(parts))
                if d.resist_reduce > 0:
                    gains.append(f"抗性穿透+{int(d.resist_reduce * 100)}%")
                if getattr(d, "ult_remain", 0) > 0:
                    gains.append("大招进行中")
                if getattr(d, "sniper_ult", 0) > 0:
                    gains.append("战术再部署")
                if getattr(d, "invuln_timer", 0) > 0:
                    gains.append("无敌")
                if getattr(d, "is_sp", False) and d.behavior == "rog":
                    gains.append({0: "火形态", 1: "冰形态", 2: "毒形态"}.get(d.rog_form, "") + "切换")
                if d.behavior == "helio":
                    gains.append("聚能棱镜·正前方友方暴击+80%/爆伤+100%")
                draw_hover_panel(screen, d.x, d.y, d.name,
                                 [(g, (170, 220, 255)) for g in gains])
                break
        # 鼠标悬停：显示怪物名字 + 当前增益/减益状态与数值（多行，共用面板绘制）
        for m in self.monsters:
            if abs(m.x + 15 - mx) < 42 and abs(m.y - my) < 42:
                status = []
                if m.freeze_timer > 0: status.append("冻结")
                if m.cold_timer > 0: status.append("寒冷(-40%速/-20%抗)")
                if m.wet_timer > 0: status.append("潮湿")
                if m.paralyze_timer > 0: status.append("麻痹")
                if m.burn_timer > 0: status.append("灼烧(+10%攻速)")
                if m.frost_timer > 0: status.append("冻伤")
                if getattr(m, "res_cut", 0.0) > 0:
                    status.append(f"减抗-{int(m.res_cut * 100)}%")
                if getattr(m, "poison_timer", 0) > 0:
                    status.append("腐蚀")
                if getattr(m, "spawn_protect", False):
                    status.append("生成保护")
                label = m.name + ("（" + "、".join(status) + "）" if status else "")
                draw_hover_panel(screen, m.x + 15, m.y, label,
                                 [(s, (255, 190, 170)) for s in status],
                                 title_border=(150, 60, 60),
                                 item_bg=(35, 20, 18), item_border=(210, 120, 90))
                break

        # 顶部信息条
        f = make_font(20)
        energy_txt = f.render(f"能量：{int(self.energy)}", True, COLOR_GOLD)
        if self.endless:
            wave_txt = f.render(f"无尽 第{self.game.endless_stage}关 · 波次：{min(self.wave_idx, self.total_waves)}/{self.total_waves}", True, COLOR_TEXT)
        else:
            wave_txt = f.render(f"波次：{min(self.wave_idx, self.total_waves)}/{self.total_waves}", True, COLOR_TEXT)
        ult_txt = f.render(("大招次数：无限" if (self.game.cheat or self.dps_mode) else f"大招次数：{self.ult_charges}/5"), True, COLOR_TEXT)
        # 顶部信息条：各文字保持间距，避免重叠（1280宽下排布）
        screen.blit(energy_txt, (170, 16))
        screen.blit(ult_txt, (300, 16))
        if self.dps_mode:
            # DPS 试炼场：中央显示计时 / 总伤害 / DPS 面板（18px紧凑排布，避免压到右侧按钮）
            sec = self.dps_frames / FPS
            dps = (self.total_damage / sec) if sec > 0 else 0
            state = "计时中" if self.dps_running else ("已停止" if self.dps_frames > 0 else "未开始")
            dp_txt = make_font(18).render(
                f"{state}  时间 {sec:.1f}s  总伤 {self.total_damage}  DPS {dps:.0f}",
                True, (255, 215, 90) if self.dps_running else COLOR_GOLD)
            screen.blit(dp_txt, (470, 18))
            self.dps_btn.draw(screen)
            self.dps_reset.draw(screen)
        else:
            screen.blit(wave_txt, (470, 16))
            if self.selected_card_uid:
                d = next(u for u in UNITS if u["uid"] == self.selected_card_uid)
                sel = f.render(f"已选：{d['name']}（点击网格放置）", True, COLOR_GREEN)
                screen.blit(sel, (600, 16))
        self.back.draw(screen)
        # 加速按钮：×2 激活时金色描边高亮（DPS试炼场不显示）
        if not self.dps_mode:
            self.speed_btn.draw(screen)
            if self.time_scale == 2:
                pygame.draw.rect(screen, COLOR_GOLD, self.speed_btn.rect, 3, border_radius=6)
        # 休憩令按钮（铲子）：启用时红色高亮，鼠标所指单位画红色框
        self.hoe_btn.draw(screen)
        if self.hoe_mode:
            pygame.draw.rect(screen, (255, 90, 90), self.hoe_btn.rect, 3, border_radius=6)
            mx, my = pygame.mouse.get_pos()
            if GRID_TOP <= my < GRID_BOTTOM:
                cx = mx // CELL_W * CELL_W + CELL_W // 2
                cy = GRID_TOP + (my - GRID_TOP) // CELL_H * CELL_H + CELL_H // 2
                ht = next((dd for dd in self.defenders
                           if abs(dd.x - cx) < 10 and abs(dd.y - cy) < 10), None)
                if ht:
                    hr = pygame.Rect(ht.x - CELL_W//2 + 4, ht.y - CELL_H//2 + 4,
                                     CELL_W - 8, CELL_H - 8)
                    pygame.draw.rect(screen, (255, 60, 60), hr, 3)
        # 操作提示（部署失败 / SP升级等）
        if self.hint:
            h = f.render(self.hint, True, COLOR_GOLD)
            screen.blit(h, (SCREEN_WIDTH//2 - h.get_width()//2, 34))

        # 底部卡牌槽位（普通战斗10格 / DPS试炼场全部单位，整体居中）
        bar_y = SCREEN_HEIGHT - 100
        if self.dps_mode:
            units_all = UNITS
            sw = (SCREEN_WIDTH - 100) // len(units_all)
            slot_x0 = (SCREEN_WIDTH - len(units_all) * sw) // 2
            for i, u in enumerate(units_all):
                slot = pygame.Rect(slot_x0 + i * sw, bar_y, sw - 4, 88)
                selected = u["uid"] == self.selected_card_uid
                border = COLOR_GOLD if selected else COLOR_GRID
                pygame.draw.rect(screen, COLOR_PANEL, slot, border_radius=8)
                pygame.draw.rect(screen, border, slot, 3 if selected else 2, border_radius=8)
                draw_unit_icon(screen, u, slot.centerx, slot.centery - 10, (36, 46))
                nm = make_font(12).render(u["name"], True, COLOR_TEXT)
                screen.blit(nm, (slot.x + 3, slot.y + 46))
                cd = self.card_cd.get(u["uid"], 0)
                if cd > 0:
                    cd_txt = make_font(15).render(f"{cd/FPS:.1f}s", True, COLOR_RED)
                    screen.blit(cd_txt, (slot.x + sw // 2 - 20, slot.y + 64))
                else:
                    en = make_font(15).render(f"{u['cost']}", True, COLOR_GOLD)
                    screen.blit(en, (slot.x + sw // 2 - 10, slot.y + 64))
        else:
            slot_x0 = (SCREEN_WIDTH - 920) // 2
            for i, u in enumerate(self.game.selected_cards):
                slot = pygame.Rect(slot_x0 + i * 92, bar_y, 88, 88)
                selected = u["uid"] == self.selected_card_uid
                border = COLOR_GOLD if selected else COLOR_GRID
                pygame.draw.rect(screen, COLOR_PANEL, slot, border_radius=8)
                pygame.draw.rect(screen, border, slot, 3 if selected else 2, border_radius=8)
                # 卡槽显示角色的完整 Q 版形象（名字用全名，SP 形态与普通形态区分开）
                draw_unit_icon(screen, u, slot.centerx, slot.centery - 10, (40, 50))
                nm = make_font(13).render(u["name"], True, COLOR_TEXT)
                screen.blit(nm, (slot.x + 6, slot.y + 46))
                cd = self.card_cd.get(u["uid"], 0)
                if cd > 0:
                    cd_txt = make_font(15).render(f"{cd/FPS:.1f}s", True, COLOR_RED)
                    screen.blit(cd_txt, (slot.x + 30, slot.y + 64))
                else:
                    en = make_font(15).render(f"{u['cost']}", True, COLOR_GOLD)
                    screen.blit(en, (slot.x + 36, slot.y + 64))

        # 底部常驻操作提示（大招 / 休憩令）
        if self.hoe_mode:
            tip_txt = "休憩令模式：点击战场中的单位铲除（不返还能量）· 再点【休憩令】收回"
        else:
            tip_txt = ("操作提示：鼠标对准单位按【空格】释放大招 · 点击卡牌再点网格放置 · "
                       "休憩令可铲除单位 · 剩余大招次数："
                       + ("无限" if (self.game.cheat or self.dps_mode) else f"{self.ult_charges}/5"))
        tip = make_font(15).render(tip_txt, True, COLOR_TEXT_DIM)
        screen.blit(tip, (SCREEN_WIDTH//2 - tip.get_width()//2, SCREEN_HEIGHT - 22))

        # 结算（无尽模式：守住本关 / 防线被攻破 两种过渡；普通模式：胜利/失败）
        if self.endless:
            if self.endless_clear:
                ov = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                ov.fill((0, 0, 0, 150))
                screen.blit(ov, (0, 0))
                msg = f"第 {self.game.endless_stage} 关守住！"
                txt = make_font(46).render(msg, True, COLOR_GREEN)
                screen.blit(txt, (SCREEN_WIDTH//2 - txt.get_width()//2, SCREEN_HEIGHT//2 - 40))
                sub = make_font(22).render("现有单位部署将保留至下一关 · 点击下方按钮重新选卡", True, COLOR_TEXT)
                screen.blit(sub, (SCREEN_WIDTH//2 - sub.get_width()//2, SCREEN_HEIGHT//2 + 6))
                self.next_btn.draw(screen)
            elif self.game_over:
                ov = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                ov.fill((0, 0, 0, 150))
                screen.blit(ov, (0, 0))
                msg = f"无尽模式结束：你撑到了第 {self.game.endless_stage} 关"
                txt = make_font(42).render(msg, True, COLOR_RED)
                screen.blit(txt, (SCREEN_WIDTH//2 - txt.get_width()//2, SCREEN_HEIGHT//2 - 40))
                ret = make_font(22).render("点击【退出战斗】返回主菜单", True, COLOR_TEXT)
                screen.blit(ret, (SCREEN_WIDTH//2 - ret.get_width()//2, SCREEN_HEIGHT//2 + 10))
        elif self.game_over:
            ov = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 150))
            screen.blit(ov, (0, 0))
            msg = "基地失守！废土怪物攻破了防线" if not self.win else "胜利！你守住了基地"
            color = COLOR_RED if not self.win else COLOR_GREEN
            txt = make_font(46).render(msg, True, color)
            screen.blit(txt, (SCREEN_WIDTH//2 - txt.get_width()//2, SCREEN_HEIGHT//2 - 40))
            ret = make_font(22).render("点击【退出战斗】返回主菜单", True, COLOR_TEXT)
            screen.blit(ret, (SCREEN_WIDTH//2 - ret.get_width()//2, SCREEN_HEIGHT//2 + 10))

# ============================================================================
# 十、主循环区：初始化 + 场景分发 + 主循环
# ============================================================================
# 【说明】在此登记所有场景。新增场景时在 SCENES 字典里加一行：
#         "名字": 场景类。主循环会自动实例化并调用其 handle_event/update/draw。
def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("废土耕地者 · Sinkland Cultivator")
    clock = pygame.time.Clock()

    game = Game()
    last_scene = None
    # 场景实例字典：新增界面在这里登记
    scenes = {
        "load":     LoadScene(game),
        "menu":     MenuScene(game),
        "guide":    GuideScene(game),     # 操作指南
        "settings": SettingsScene(game),
        "level":    LevelSelectScene(game),
        "codex":    CodexScene(game),
        "card":     CardSelectScene(game),
        "sandbox":  SandboxScene(game),   # 沙盒：只创建一次，进出主界面保留布置
        "battle":   None,   # 战斗场景需要每次重新创建（因为关卡/选卡会变）
    }

    running = True
    while running:
        dt = clock.tick(FPS)
        # 场景切换：进入 battle / card 时每次都重建（关卡、选卡会变化）
        if game.scene == "battle" and last_scene != "battle":
            scenes["battle"] = BattleScene(game, dps_mode=game.dps_mode)
            game.dps_mode = False     # dps_mode 一次性消费，下次进入战斗恢复普通模式
        if game.scene == "card" and last_scene != "card":
            scenes["card"] = CardSelectScene(game)
        last_scene = game.scene

        cur = scenes[game.scene]
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            cur.handle_event(event)
        cur.update()
        cur.draw(screen)
        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()
