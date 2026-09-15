#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 数据/地点规则.csv —— 全部火星地点的「定位规则」唯一来源。
改地点：改这里的表，重跑本脚本，再跑 scripts/20_地点定位.py。

规则语法（字段之间用冒号，坐标用分号）：
  iau:地名                  IAU 官方中心点
  iau_edge:地名:方位         IAU 地貌边缘（中心 + 半径，方位 N/S/E/W/NE…）
  summit:地名               IAU 范围内最高点
  caldera:地名              山顶火山口中心
  caldera_rim:地名:方位      山顶火山口的某侧边缘
  scarp_top:地名:方位        山体基座悬崖的崖顶（从山心沿方位出发，最陡一段的上沿）
  floor:纬;经;半径km         半径内最低点（谷地城镇）
  map:纬;经                 正典地图目测位置（没有更好依据时）
  point:纬;经               精确已知坐标（着陆器）
  shore:水体:岸侧:纬;经       离给定点最近的、在指定岸侧的岸线点
  inland:水体:岸侧:纬;经:km   先找岸线点，再沿岸侧方向往陆上走 km
  wet_snap:水体:纬;经         正典图位置；若落在水里，推到最近岸
  near:地点id:方位:km        相对另一个地点
  ref_shore:水体:岸侧:地点id:经度差   参考另一地点的经度，找它旁边的岸线点
  gap:掩膜A:掩膜B            两块水体最近处（闸坝址）
  gap_west:掩膜              该掩膜最大水块与其西侧水块的最近处
  cutface:掩膜:东经:north|south   水体在某条经线截断面上的北/南出口
  centroid:掩膜              水体质心
  orbital                  轨道设施，无地表坐标
水体/掩膜名：borealis hellas marineris marineris_ius marineris_mid marineris_eos lake_innsbruck lake_mutch
"""
import csv, pathlib
H = ["id","中文名","英文名","类别","阵营","等级","正典","规则","依附","出处","正典描述","旧纬度","旧东经"]
T = [
# ── 水手峡谷工程设施（先算，城镇会引用）──────────────────────────────
("ius_locks_w","Ius 船闸群（西闸）","Ius Locks (west)","闸坝","锈色中国",1,"正文+地图","gap_end:marineris_ius:marineris_mid","Ius 段水面东端，运河西口","ITW p.22 · p22 图","正典：西半部的巨型船闸阻止水在东端积聚",-12.7,277.8),
("ius_locks_e","Ius 船闸群（东闸）","Ius Locks (east)","闸坝","锈色中国",1,"正文+地图","gap_end:marineris_mid:marineris_ius","Melas 段水面西端，运河东口；两闸之间是约 170 km 的越岭运河","ITW p.22 · p22 图","",-11.6,279.1),
("capri_dam","Capri 峡谷大坝","Capri Chasma Dam","闸坝","火星联邦（美）",1,"正文+地图","cutface:marineris_eos:318.0:north","厄俄斯湖东北出口，下泄水经河道供给红湖","ITW p.25 · p22 图","红湖由 Capri 峡谷大坝的下泄水供给；罗宾逊城在坝西侧",-9.7,312.4),
("eos_dam","Eos 大坝","Eos Dam","闸坝","火星联邦（美）",1,"仅地图","cutface:marineris_eos:318.0:south","厄俄斯湖东南出口","p22 图","",-14.7,317.3),
# ── 塔西斯 ────────────────────────────────────────────────────────
("new_shanghai","新上海","New Shanghai","城市","锈色中国",1,"正文+地图","caldera_rim:Pavonis Mons:S","Pavonis Mons 山顶火山口南缘","ITW p.21–22","火星最大城市，太空电梯地面站；一号穹顶北缘能向下看三英里到火山口底",0.8,246.6),
("elevator","太空电梯地面基座","Space Elevator ground station","设施","锈色中国",1,"正文","near:new_shanghai:N:8.4","新上海六穹顶环绕的基座建筑群；一号穹顶北缘压在火山口壁顶（MOLA 128 px/度：壁顶 0.19°N，坑底 9,270 m，落差 4,100 m ≈ 正典「三英里」）","ITW p.21, 27","六个穹顶围绕电梯基座；缆索断裂时新上海及东郊首当其冲","",""),
("nix_olympica","尼克斯奥林匹卡","Nix Olympica","城市","独立",1,"正文+地图","scarp_top:Olympus Mons:S","Olympus Mons 南坡崖顶","ITW p.17, 44","独立大学城，CR 2；位于南坡崖顶，俯瞰塔西斯；有专用支线接赤道铁路",18.7,226.2),
("univ_mars","火星大学","University of Mars","设施","独立",2,"正文","near:nix_olympica:N:1","尼克斯奥林匹卡城内","ITW p.17","2066 年成立；地球化系无可匹敌","",""),
("zeus_resort","宙斯旅游度假区（主设施）","Zeus Tourist Resort","设施","独立",2,"正文+地图","near:nix_olympica:E:1.6","尼克斯奥林匹卡以东一英里的崖缘，电车相连","ITW p.17, 20","登山、攀崖、滑雪、飞艇游览",18.7,224.0),
("zeus_caldera","宙斯度假区·火山口分部","Zeus Resort (caldera branch)","设施","独立",3,"正文","caldera:Olympus Mons","Olympus Mons 山顶火山口","ITW p.20","度假区分支之一","",""),
("aralqi","Aralqi","Aralqi","城镇","锈色中国",3,"正文+地图","iau:Poynting","Poynting 陨坑（Pavonis 以北、Ascraeus 以西）","ITW p.23","",4.0,253.0),
("rizhao","日照","Rizhao","城镇","锈色中国（按命名推断）",3,"仅地图","map:2;250","Ascraeus Mons 东南","p19 图","",2.0,250.0),
("heze","菏泽","Heze","城镇","锈色中国（按命名推断）",3,"仅地图","map:-5;236","Arsia Mons 以西","p19 图","",-5.0,236.0),
("as_sulaymi","As Sulaymi","As Sulaymi","城镇","沙特",3,"正文+地图","map:-14.7;233.6","Daedalia Planum，Arsia 以南","ITW p.26 · p19 图","沙特游牧者建立的商旅交汇点、次级太空港",-14.7,233.6),
("liangzhen","Liangzhen","Liangzhen","城镇","锈色中国",2,"正文+地图","shore:borealis:ANY:25;210","北方海岸，Olympus Mons 以西；锈色中国西部边界","ITW p.23","居民觉得被政府抛弃，一直争取修铁路支线（没有支线）",25.0,205.0),
("oita","大分","Oita","城镇","日本（按命名推断）",3,"仅地图","shore:borealis:W:28;196","Amazonis 湾西岸","p19 图","",28.0,196.0),
("albor_home","阿尔博尔山顶独居庄园","Albor Tholus summit home","庄园","火星百万富翁",3,"正文","summit:Albor Tholus","Albor Tholus 峰顶","ITW p.47","一位富豪的单人住宅","",""),
("urumqi","乌鲁木齐","Urumqi","城镇","锈色中国（按命名推断）",3,"仅地图","map:-11.7;252.9","诺克提斯迷宫西南","p22 图","",-11.7,252.9),
("ge_gyai","革吉","Ge'gyai","城镇","锈色中国",3,"正文+地图","floor:-8.7;258.1;60","诺克提斯迷宫中的一条谷地","ITW p.23","农业，专攻果树，产好葡萄酒与苹果酒",-8.7,258.1),
("wudu","武都","Wudu","城镇","锈色中国",2,"正文+地图","iau:Syria Planum","Syria Planum，诺克提斯以南","ITW p.23","小麦带核心；「新中国」活动中心，十二局特工云集",-12.1,256.6),
("guxiang","故乡","Guxiang","遗址","锈色中国",2,"正文+地图","map:-1.7;260.6","诺克提斯北缘台地（正典图）","ITW p.9 · p22 图","中国第一个火星基地",-1.7,260.6),
("haiyuan","海源城","Haiyuan City","城市","锈色中国",1,"正文+地图","iau_edge:Oudemans:NE","Oudemans 陨坑东北缘；提托尼乌姆湖在其北","ITW p.22–23","锈色中国首府，梯田港城，十二局总部",-9.8,268.2),
("nantong","南通","Nantong","城镇","锈色中国（按命名推断）",3,"新闻+地图","iau:Echus Chasma","Echus River（Echus Chasma）；卡塞谷的源头","p19 图 · Teralogos News 2100 Q4","2100 年 12 月 18 日电头；劫道土匪的藏身处在南通周边的崎岖地带",10.0,278.0),
("hanggin_qi","杭锦旗","Hanggin Qi","城镇","锈色中国",2,"正文+地图","shore:marineris_ius:N:-6.8;277.0","水手峡谷海北岸，Ius 段","ITW p.23","矿业城镇，硝酸盐与铂；尾矿把褐色的海水都染了色",-7.9,274.5),
("harbin","哈尔滨","Harbin","城镇","锈色中国（按命名推断）",3,"仅地图","shore:marineris_mid:S:-9.5;283.8","Ius 船闸与 Melas 之间的南岸","p22 图","",-15.6,280.0),
# ── 水手峡谷中东段 ────────────────────────────────────────────────
("bako","巴科","Bako","城镇","非洲（埃塞俄比亚）",2,"正文+地图","shore:marineris_mid:W:-6.0;286.0","坎多尔湖西岸","ITW p.26","火星非洲人中心；本土软件业 80% 出自这里",-6.5,284.5),
("port_lowell","洛厄尔港","Port Lowell","城市","企业（MDC）",1,"正文+地图","shore:marineris_mid:E:-7.8;289.6","坎多尔湖东南岸（湖口，濒 Melas）","ITW p.23, 26","企业城邦，租地给各国；欧洲人最集中",-11.1,289.7),
("vlore","发罗拉","Vlore","城镇","欧盟（按命名推断）",3,"仅地图","inland:marineris_mid:E:-6.4;293.4:25","坎多尔湖以东的台地，铁路经过","p22 图","",-9.2,294.5),
("santo_tomas","圣托马斯","Santo Tomas","城镇","火星联邦（美）",2,"正文+地图","shore:marineris_mid:S:-13.0;288.2","水手峡谷海南岸，Nia Fossae 一带","ITW p.25","造船城；常处在南侧崖壁的阴影里",-17.8,288.0),
("fortuna","福尔图纳","Fortuna","城镇","火星联邦（按命名推断）",3,"仅地图","shore:marineris_mid:N:-12.0;301.6","Coprates 北岸","p22 图","",-14.7,301.6),
("chester","切斯特栖息地","Chester Habitat","城镇","火星联邦（美）",2,"正文+地图","inland:marineris_mid:N:-11.5;302.2:161","水手峡谷以北 100 英里，Ophir Planum","ITW p.24","农户集会地；赤道铁路穿镇而过，粮食在此装车",-12.2,303.9),
("robinson","罗宾逊城","Robinson City","城市","火星联邦（美）",1,"正文+地图","ref_shore:marineris_eos:N:capri_dam:-0.7","厄俄斯湖北岸，Capri 大坝以西","ITW p.24","穹顶城市；美方最大栖息地",-9.8,311.1),
("plymouth","普利茅斯","Plymouth","遗址","火星联邦（美）",2,"正文+地图","rim:marineris_eos:S:-16.0;316.0","水手峡谷东端以南，俯瞰厄俄斯峡谷","ITW p.9–10","美国第一个火星基地；Frank Roth 出生地",-18.9,306.2),
("burroughs","巴勒斯火星历史博物馆","Burroughs Museum of Martian History","设施","火星联邦（美）",3,"正文","near:plymouth:W:2","普利茅斯","ITW p.58","火星最大的综合性公共博物馆","",""),
("anchorage","安克雷奇","Anchorage","城镇","火星联邦（按命名推断）",3,"仅地图","shore:marineris_eos:S:-16.0;317.6","厄俄斯湖南岸，Eos 大坝以南","p22 图","",-17.1,315.8),
("red_lake","红湖","Red Lake","城镇","火星联邦（美）",2,"正文+地图","iau_edge:Innsbruck:W","Innsbruck 陨坑湖西岸","ITW p.25","水产与海带养殖；湖与主河道之间有围隔",-5.6,314.7),
("fort_meier","迈尔堡","Fort Meier","军事","火星联邦（美陆军）",2,"正文","near:red_lake:N:35","紧邻红湖城外（方位与距离为推定，制图上与红湖符号错开）","ITW p.25, 46","美国陆军游骑兵驻火星部队",""," "),
("timbuktu","廷巴克图","Timbuktu","城镇","火星联邦（美）",3,"正文+地图","iau:Timbuktu","赞西高地内同名陨坑","ITW p.25","科研社区，粮食作物遗传学；Burton 总督的中学母校",-2.6,315.2),
# ── 赞西 / 克律塞 / 北方海西岸 ─────────────────────────────────────
("zhigansk","日甘斯克","Zhigansk","城市","独立（原俄罗斯）",2,"正文+地图","shore:borealis:ANY:19;311","赞西高地北部，北方海畔","ITW p.24","2064 年火星第一个宣布独立的殖民地；Free Mars 大本营",20.0,310.0),
("sharona","沙罗纳","Sharona","城镇","火星联邦（美）",2,"正文+地图","iau_edge:Sharonov:N","Sharonov 湾（原 Sharonov 陨坑）坑壁","ITW p.25","运冰机终点、北方海水文研究中心；房子每几年往坑壁上搬一次",27.3,301.5),
("new_amsterdam","新阿姆斯特丹","New Amsterdam","城镇","荷兰",3,"正文+地图","shore:borealis:ANY:15.7;318.0","Shalbatan 河（Shalbatana Vallis）河口","ITW p.26","几百人，制药与生物技术实验室",13.0,317.0),
("rockwood","罗克伍德","Rockwood","城镇","火星联邦（按命名推断）",3,"仅地图","shore:borealis:S:18;323","克律塞湾南岸（东段）","p19 图","",15.0,315.0),
("shibetsu","士别","Shibetsu","城镇","日本",3,"正文+地图","iau:Ares Vallis","Ares Vallis，赞西高地以东","ITW p.26","清品公司火星车工厂；牛排馆口碑好",10.4,334.0),
("dayville","戴维尔","Dayville","城镇","火星联邦（按命名推断）",3,"仅地图","wet_snap:borealis:40;337","Acidalia Planitia","p19 图","",40.0,337.0),
("christiana","克里斯蒂安娜","Christiana","城镇","火星联邦/北欧（按命名推断）",3,"仅地图","map:-13;337","Margaritifer Terra","p19 图","",-13.0,337.0),
("viking1","维京公园·海盗 1 号着陆点","Viking Park / Viking 1 Lander","遗址","火星联邦（美）",2,"正文","point:22.697;311.813","克律塞平原","ITW p.26","禁止开发的公园；美方正在修堤防海",22.697,311.813),
("sagan","卡尔·萨根纪念站（火星探路者）","Carl Sagan Memorial Station","遗址","火星联邦（美）",3,"正文","point:19.13;326.79","阿瑞斯谷口","ITW p.26","维京公园的第二处遗址",19.13,326.79),
("kasei","卡塞谷（劫道土匪出没区）","Kasei Valles","区域","—",3,"正文","iau:Kasei Valles","Kasei Valles","Teralogos News 2100 Q4","2100 年 12 月：土匪劫掠地面运输车队、袭击沙特商队 Beni Khasim；美方兼职法警追踪、陆军游骑兵抓捕","",""),
# ── 伊利瑟姆与东半球 ─────────────────────────────────────────────
("peru_core","秘鲁殖民地核心区","Peruvian colony core","区域","秘鲁",2,"正文+地图","map:25;140","Elysium（西坡）","ITW p.48–49","人口个位数百分比，却主导伊利瑟姆与火星大众文化",25.0,140.0),
("moyobamba","莫约班巴","Moyobamba","城市","秘鲁",2,"正文+地图","shore:borealis:ANY:34;124.5","Granicus Valles 注入北方海处","ITW p.48","生物地球化设施；火星最好的动物园与植物园",30.0,130.0),
("stygis","冥河城","Stygis Ciudad","城市","秘鲁",2,"正文+地图","map:30;150","伊利瑟姆，Hecates Tholus 一带","ITW p.48","托管马丘比丘虚拟重建——火星最受欢迎的虚拟世界",30.0,150.0),
("ica_nova","新伊卡","Ica Nova","城镇","秘鲁（按命名推断）",3,"仅地图","map:18;150","Albor Tholus 旁","p20 图","",18.0,150.0),
("escalante","埃斯卡兰特站","Escalante Station","设施","火星联邦（美）",2,"正文+地图","iau:Escalante","Escalante 陨坑（赤道上）","ITW p.27, 49","赤道铁路最后一段合龙点，2100 年 7 月下旬通车庆典",0.1,115.1),
("clarke","克拉克","Clarke","城镇","火星联邦（按命名推断）",3,"仅地图","wet_snap:borealis:48.165;139.655","Adamas 湾以北，Mie 陨坑一带","p20 图","",48.0,140.0),
("dao_city","道城","Dao City","城镇","混杂（按命名推断）",3,"仅地图","floor:-38.6;83.2;80","Dao 河（Dao Vallis）河口","p20 图","",-33.2,93.3),
("hellas_shore","海拉斯海沿岸聚落带","Hellas Sea rim settlements","区域","美、欧、南美为主",2,"正文","shore:hellas:N:-30;60","海拉斯海沿岸","ITW p.15, 25","科学家密度堪比尼克斯奥林匹卡；化石市场",-28.0,74.1),
("syrtis_estates","大瑟提斯以北庄园区","Syrtis Major estates","庄园","火星百万富翁",3,"正文","point:19.4;67.1","Syrtis Major Planum 北缘","ITW p.47","数千英亩精心造景的私人庄园，数百名仆人","",""),
("syrtis_desert","大瑟提斯荒漠（矿区·超级坦克决斗场）","Syrtis Major desert","区域","企业 / 百万富翁",3,"正文","iau:Syrtis Major Planum","Syrtis Major Planum","ITW p.25, 47–48","少数矿业公司；一年两度的超级坦克决斗","",""),
# ── 两极与其他 ───────────────────────────────────────────────────
("north_cap","北极冰盖（自动钻机采冰）","Planum Boreum","自然地标","—",2,"正文","iau:Planum Boreum","北极","ITW p.26","露出北方海，一圈窄黑沙滩；预计 2110 年前融尽",88.0,15.0),
("olympia_undae","奥林匹亚沙丘带","Olympia Undae","自然地标","—",3,"地图","iau:Olympia Undae","北极环带","p19 图（误作 Olympia Planitia）","",80.9,178.2),
("south_cap","南极冰盖（科研与地球化站）","Planum Australe","自然地标","—",3,"正文","iau:Planum Australe","南极","ITW p.26","干冰只剩几百码厚；比北极高三英里",-83.0,160.0),
("argyre","阿吉尔盆地（干）","Argyre Planitia","自然地标","—",3,"正文","iau:Argyre Planitia","南半球","ITW p.26","四周环山，降水外流，中心干燥",-49.7,316.0),
("schiaparelli","斯基亚帕雷利陨坑","Schiaparelli","自然地标","—",3,"—","iau:Schiaparelli","赤道","—","正典的「Schiaparelli 船厂」是轨道设施，与此坑无关",-2.7,16.8),
# ── 水体 ─────────────────────────────────────────────────────────
("lake_tithonium","提托尼乌姆湖","Lake Tithonium","水体","—",2,"正文+地图","iau:Tithonium Chasma","海源城以北的「死胡同」支流","ITW p.22","游艇与游客为主",-4.6,275.5),
("lake_candor","坎多尔湖","Lake Candor","水体","—",2,"正文+地图","centroid:marineris_mid:-8.0;-3.0;284.5;296.0","水手峡谷海北支（湖心取水面质心，IAU 中心落在 Candor Mensa 台地上）","ITW p.23","",-6.5,284.5),
("lake_eos","厄俄斯湖","Lake Eos","水体","—",2,"正文+地图","centroid:marineris_eos","水手峡谷海东端","ITW p.24","",-12.0,313.5),
("hebes_lake","赫柏湖（Hebes Chasma）","Hebes Chasma","水体","—",3,"仅地图","centroid:marineris_mid:-2.2;0.2;281.4;286.7","水手峡谷以北的封闭峡谷（湖心取水面质心）","p22 图（误作 Herbes）","",-1.1,283.5),
("mutch_lake","Mutch 陨坑湖","Mutch Crater lake","水体","—",3,"仅地图","iau:Mutch","赞西高地","p22 图","",0.6,304.7),
("gangis","恒河（Gangis River）","Ganges Chasma","水体","—",3,"仅地图","iau:Ganges Chasma","流向 Capri 的河谷","p22 图（Gangis River）","",-7.6,313.0),
("echus_river","Echus 河","Echus Chasma","水体","—",3,"仅地图","iau:Echus Chasma","Lunae Planum 西缘","p19 图","",10.0,278.0),
("noctis","诺克提斯迷宫","Noctis Labyrinthus","自然地标","—",2,"正文+地图","iau:Noctis Labyrinthus","塔西斯东坡","ITW p.22","峡谷高于海面，湿谷青翠、散布中国栖息地",-6.5,258.3),
]
p = pathlib.Path(__file__).with_name("地点规则.csv")
with open(p, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f); w.writerow(H)
    for row in T: w.writerow([str(x).strip() for x in row])
print(f"{p.name}: {len(T)} 条")
