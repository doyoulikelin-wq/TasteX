#!/usr/bin/env python3
"""Reviewed processing index for the existing 253 book evidence records.

The inclusion decisions and effect directions below are curated explicitly.
No keyword classifier creates causal claims, no numeric flavor vector is made,
and the original evidence object remains unchanged in every included record.
"""
from pathlib import Path
from collections import Counter
import copy
import json
import sys

STUDIO = Path(__file__).resolve().parents[1]
ROOT = STUDIO.parent
sys.path.insert(0, str(ROOT / 'tmp/flavor_catalog_deps'))
from opencc import OpenCC
S = OpenCC('t2s').convert
SOURCE = json.loads((ROOT / 'output/flavor/食材风味属性_结构化数据.json').read_text())
EVIDENCE = {r['evidence_id']: r for r in SOURCE['evidence']}
PAGES = {p['pdf_page']: p for p in json.loads((ROOT / 'tmp/pdfs/flavor_source/pages.json').read_text())}
FULL = json.loads((STUDIO / 'data/evidence-full.json').read_text())
assert FULL['source'] == SOURCE, 'The preserved evidence source has changed.'
records = []

def fx(domain, labels, direction='conditional', detail=''):
    """One explicit reviewed assertion can index several distinct descriptors."""
    return [dict(domain=domain, label=label, direction=direction,
                 detail=detail or ('处理后状态中的描述，未报告相对变化。' if direction == 'conditional' else '书中定性方向，未提供变化幅度。'))
            for label in labels.split('、')]

def a(labels, direction='conditional', detail=''): return fx('aroma', labels, direction, detail)
def c(labels, direction='conditional', detail=''): return fx('chemical', labels, direction, detail)
def t(labels, direction='conditional', detail=''): return fx('taste', labels, direction, detail)
def x(labels, direction='conditional', detail=''): return fx('texture', labels, direction, detail)
def o(labels, direction='conditional', detail=''): return fx('other', labels, direction, detail)
def color(labels, direction='conditional', detail=''): return fx('color', labels, direction, detail)

def add(n, methods, kind, before, after, summary, effects, *, conditions='', mechanism='', limitations='', names=None, suffix='', values=None):
    eid = f'E{n:04d}'
    original = EVIDENCE[eid]
    assert original['pdf_page'] in PAGES
    # Ripening/harvest is a material condition, not a demonstrated processing
    # intervention. Preserve its direction, but keep it outside change counts.
    method_list = ['成熟/采收条件' if m == '成熟/采收' else m for m in methods.split('、')]
    if method_list == ['成熟/采收条件']:
        kind = 'condition_dependency'
    values = copy.deepcopy([v for v in SOURCE['reported_numeric_values'] if v['evidence_id'] == eid] + (values or []))
    item = dict(
        id=f'PB-{eid}' + (f'-{suffix}' if suffix else ''),
        title=S(original['ingredient']) + ' · ' + after,
        ingredientNames=names or [S(original['ingredient'])],
        methods=method_list, recordKind=kind,
        before=before, after=after,
        conditions=conditions or (S(original['state']) + '。温度、时间、用量及样品条件未完整报告。'),
        mechanism=mechanism or '本条没有给出可独立核验的完整反应机制。',
        summary=summary,
        limitations='；'.join(filter(None, [S(original['note']), limitations,
            '仅为书中证据的整理，未独立重复实验；不能由此计算任意加工条件的风味增量。'])),
        effects=effects,
        source=dict(kind='book', evidenceIds=[eid], pdfPages=[original['pdf_page']],
                    bookPages=[original['book_page']], title='食物風味搭配科學', url=''),
        original=copy.deepcopy(original), reportedValues=values,
        evidenceLevel=('书中条件或描述数值' if values else '书中定性描述'),
        extractionScope='existing_extracted_evidence',
    )
    if kind == 'state_profile':
        assert before == '基线未报告', item['id']
        assert all(e['direction'] == 'conditional' for e in effects), item['id']
        item['limitations'] += '；此条仅是指定处理后状态的轮廓，不能读作加工前后增减。'
    records.append(item)

# Each call is an explicit reading decision, in evidence order.
add(5,'储藏、成熟/采收','condition_dependency','条件未限定的苹果','不同成熟与贮藏条件',
    '书中指出成熟、贮藏方法以及空间氧气和二氧化碳浓度均影响苹果风味。',
    a('水果气味、花卉气味、青绿气味、香料气味、乳酪气味','conditional','方向依品种、生长、采收及贮藏共同决定；未报告各条件的独立效应。'),
    mechanism='书中将树上成熟时间与脂肪酸生成和风味复杂度联系。')
add(10,'熟制（方式未说明）','change','生芹菜根','熟芹菜根','煮熟后呈微甜并有鲜奶油般质地。',
    t('甜味','emerge')+x('奶油般质地','emerge'), names=['芹菜根','熟芹菜根'])
add(12,'熟制（方式未说明）','state_profile','基线未报告','熟芹菜根','熟芹菜根与奶油乳酪共有香草醛以及花香玫瑰调。',
    a('香草气味、花卉气味'), names=['芹菜根','熟芹菜根'], limitations='与另一食材共享分子，不证明这些分子全由加热新生。')
add(13,'其他处理（未详述）','state_profile','基线未报告','加工后大溪地香草','书中加工后大溪地香草轮廓包含香草、大茴香和花卉；比例保留原分母。',a('香草气味、大茴香气味、花卉气味'))
add(14,'其他处理（未详述）','state_profile','基线未报告','加工后波本香草','书述香草醛占复杂香气轮廓的 82%，不是荚重量的 82%。',a('香草气味'))
add(15,'其他处理（未详述）','state_profile','基线未报告','加工后波本香草的辅助香气','加工后波本香草另有木质、巴萨米克、乳酪、椰子、桃子、奶油和烟熏调。',a('木质气味、巴萨米克气味、乳酪气味、椰子气味、桃子气味、奶油气味、烟熏气味'))
add(16,'混合/乳化','condition_dependency','香草醛；配方基质未限定','高脂基质中的香草醛','书述香草醛在鲜奶油等高脂基质中香气更强、释放更久。',
    a('香草气味','increase')+o('香气持续时间','increase'), names=['香草醛','鲜奶油'],
    mechanism='书中以香草醛脂溶性解释基质效应。', limitations='基质改变的条件效应，不是香草的永久固有属性；未给配方比例。')
add(17,'发酵、干燥、烘烤、精炼','condition_dependency','可可原料与工艺未控制','不同产地和工艺的黑巧克力','黑巧克力风味受品种、产地、成熟、发酵、干燥、烘烤和精炼共同影响。',
    a('水果气味、花卉气味、坚果气味','conditional','产地样本比较，不能分离成某一道工艺的独立因果效应。'),limitations='秘鲁与哥斯达黎加只是书中样本比较，不是产地定律。')
add(18,'发酵','change','未说明发酵时长的可可豆','可可豆发酵及延长发酵','发酵形成水果、柑橘、花卉、乳酪、杏仁类新分子；较长发酵增强水果与乳酪，过久可能产生霉味或鱼腥。',
    a('水果气味、柑橘气味、花卉气味、乳酪气味、杏仁气味','emerge')+
    a('水果气味、乳酪气味','increase','相对较短发酵，书中未给天数。')+
    a('霉味、鱼腥气味','conditional','仅指发酵过久的可能缺陷；不是所有发酵必然产生。'))
add(19,'巧克力制作（工序未拆分）','change','未指定工序的巧克力原料','牛奶巧克力制作过程','制作过程中形成草莓呋喃酮，书述其浓度高于草莓中；实际浓度未报告。',
    c('草莓呋喃酮','emerge')+a('草莓气味、凤梨气味、焦糖气味','conditional','描述该分子的香气联系，不等于整份巧克力三种感官强度均上升。'))
add(22,'水煮、蒸制','change','生花椰菜','水煮或蒸煮花椰菜','原有硫调转向熟马铃薯和蘑菇型蔬菜气味，升温出现更多泥土和烘烤化合物。',
    a('硫气味','change')+a('熟马铃薯气味、蘑菇气味','emerge')+c('泥土气味相关化合物、烘烤气味相关化合物','increase'),
    limitations='水煮和蒸煮未分别定量；原属性中的刺鼻与奶油保留于原始对象，未赋增减方向。')
add(23,'水煮','change','花椰菜原料','水煮花椰菜的香气流失','书述亲水香气分子进入水中并挥发。',c('亲水性香气分子','decrease'),
    mechanism='书中提出水相溶出与挥发解释。', suffix='water')
add(23,'油脂烹调、烘烤','condition_dependency','水煮花椰菜（比较基线）','脂肪烹调或烘烤花椰菜','相对水煮，书述脂肪烹调或烘烤可保留更多蔬菜风味。',
    a('蔬菜气味','increase','相对水煮，不是相对生花椰菜的绝对增加。'),suffix='fat')
add(24,'成熟/采收','change','未成熟草莓','成熟草莓','成熟时呋喃酮浓度上升，香气随浓度由果香向焦糖、棉花糖变化。',
    c('呋喃酮','increase')+a('水果气味、焦糖气味、棉花糖气味','conditional','气味描述依赖分子浓度，不能赋固定换算系数。'),limitations='生物成熟条件记录，不代表人为加工实验。')
add(25,'切碎/破碎、加热（方式未说明）','change','草莓原料','捣碎或加热草莓','捣碎与加热可引发反应；烹调时果香、焦糖及其他香气分子增加。',
    c('水果气味相关化合物、焦糖气味相关化合物','increase')+a('花卉气味、乳酪气味、奶油气味、坚果气味','conditional','原文列出伴随香气，未逐一报告增幅。'),
    limitations='捣碎和加热未分别给出独立效应，不能将全部分子增加归因于仅捣碎。')
add(27,'加热（方式未说明）','condition_dependency','新鲜甜罗勒','高温处理甜罗勒','书述高温容易破坏甜罗勒的细致风味。',a('细致香气','decrease'),limitations='原分子列表是新鲜叶轮廓，未逐分子证明热降解方向。')
add(30,'加热（方式未说明）','condition_dependency','新鲜泰国罗勒','烹调末段加入','书中建议在烹调末段加入泰国罗勒，并描述其大茴香气味。',
    a('大茴香气味','conditional','烹调用法建议，未报告早加入和晚加入的量化或感官对照。'),limitations='本条是处理建议及状态信息，不是经实验验证的增香效应。')
add(35,'桶陈/熟成','change','未桶陈龙舌兰酒','橡木桶陈龙舌兰酒','桶陈引入内酯，丁香、香草及烟熏相关浓度升高，同时其他某些化合物挥发。',
    c('橡木内酯、威士忌内酯','emerge')+c('丁香气味相关化合物、香草气味相关化合物、烟熏气味相关化合物','increase')+
    c('其他挥发物（未列名）','decrease')+a('坚果气味、零陵香豆气味、椰子气味','conditional'))
add(36,'榨汁','state_profile','基线未报告','现榨柠檬汁','现榨汁以柠檬香为主，另有木质、樟脑、松木、花卉、青绿、水果和辛辣调。',a('柑橘气味、木质气味、樟脑气味、松木气味、花卉气味、青绿气味、水果气味、香料气味'),names=['柠檬','柠檬汁'])
add(37,'榨汁','state_profile','基线未报告','莱姆汁','书比较莱姆汁与柠檬汁：同 pH 但莱姆汁更清新，涉及青草、樟脑和薄荷等香气。',a('青绿气味、青草气味、樟脑气味、薄荷气味')+o('清凉感'),names=['莱姆','莱姆汁'],limitations='跨食材果汁比较，不是榨汁前后对照；相同 pH 未给具体数值。')
add(39,'干燥','condition_dependency','秘鲁黄辣椒；新鲜或干制状态未拆开','新鲜或晒干米拉索','书中同条同时提及新鲜黄辣椒和晒干米拉索；保留状态不确定性及品种辣度范围。',a('苹果气味、凤梨气味、木质气味、乳酪气味','conditional')+o('辣感','conditional','SHU 为书中品种范围，并非新鲜与干燥的比较增量。'),limitations='未按新鲜/晒干分配测值，不可据此推断干燥增辣幅度。')
add(43,'成熟/采收','change','青色未熟哈瓦那辣椒','红色成熟哈瓦那辣椒','成熟转红后青绿脂肪调减少，花卉调增加；辣度区间保留为品种状态描述。',a('青绿脂肪气味','decrease')+a('花卉气味','increase'),names=['红哈瓦那辣椒','青哈瓦那辣椒'],limitations='SHU 不是成熟过程中辣度变化的实验曲线。')
add(45,'切碎/破碎','condition_dependency','新鲜香菜叶','捣碎香菜叶','书述捣碎可能减轻部分人感到的肥皂气味。',a('肥皂气味','decrease','受感知者差异影响；不是每个人都感到肥皂味。'),names=['香菜叶'],limitations='个体感知差异和书中处理建议，未报告人群试验。')
add(46,'烘烤、网烤','change','多佛比目鱼原料','烘烤或网烤多佛比目鱼','烤制可形成新分子，成品仍有鲜鱼青草、脂肪与黄瓜调。',c('新香气分子（未逐项测定）','emerge')+a('奶油气味、青草气味、脂肪气味、黄瓜气味、鱼腥气味','conditional'),limitations='苯甲醛只是书中所述可能微甜来源，不作确定甜味因果。')
add(47,'成熟/采收','change','未熟甜椒','成熟红甜椒','成熟可使具果香的青绿分子出现更多。',c('果香青绿相关化合物','increase'),names=['红甜椒'],limitations='不同颜色与品种条件未量化控制。')
add(48,'干燥、研磨','change','鲜甜椒','干燥磨粉红椒粉','干燥磨粉后典型甜椒吡嗪减少，焦糖、枫糖、紫罗兰和蜂蜜气味增多。',c('典型甜椒吡嗪','decrease')+a('焦糖气味、枫糖气味、花卉气味、蜂蜜气味','increase'),names=['红椒粉','甜椒'],limitations='不能将烟熏调赋予所有红椒粉。')
add(49,'切碎/破碎','change','新剥完整蒜瓣','切片、捣碎或剁碎大蒜','细胞破坏后形成新的硫味分子，出现蒜、洋葱与刺鼻感。',c('蒜素','emerge')+a('硫气味、蒜气味、洋葱气味','emerge')+o('刺鼻感','emerge'),mechanism='蒜胺酸与蒜胺酸酶接触，形成蒜素并进一步出现含硫风味分子。',names=['大蒜','蒜末','蒜泥'])
add(51,'烘烤','change','新鲜大蒜','烤蒜泥','强烈青绿蒜味下降，烘烤、焦糖与坚果调增加，另有水果、花卉和香料调。',a('青绿蒜气味','decrease')+a('烘烤气味、焦糖气味、坚果气味','increase')+a('水果气味、花卉气味、香料气味','conditional','成品辅助香气，未逐一给出相对生蒜的增减方向。'),mechanism='书中以梅纳反应解释新化合物形成与蒜味柔和。',names=['大蒜','烤蒜泥'])
add(52,'切碎/破碎','state_profile','基线未报告','新鲜蒜末','新鲜蒜末具有硫味、蔬菜和果香；2-甲基丁酸乙酯与凤梨、芒果形成香气联系。',a('硫气味、蔬菜气味、水果气味'),names=['大蒜','蒜末'])
add(53,'切碎/破碎','state_profile','基线未报告','新鲜蒜末图示轮廓','图中洋葱与大蒜为主，脂肪、黄瓜、青草与青绿为辅助描述。',a('洋葱气味、蒜气味、脂肪气味、黄瓜气味、青草气味、青绿气味'),names=['大蒜','蒜末'],limitations='原图无刻度，未从面积换算任何百分比。')
add(54,'温热熟成','change','新鲜蒜头','湿热陈放黑蒜泥','约 60°C 湿热陈放 4—6 周，硫味下降，出现甜、鲜、水果与复杂巧克力相关风味；焦糖调少于烤蒜。',
    c('含硫气味化合物','decrease')+o('刺鼻辣口感','decrease')+t('甜味、鲜味','conditional','书中黑蒜成品的味觉描述，没有味觉前后对照测值。')+a('水果气味','increase')+a('巧克力气味','conditional','3-甲基丁醛使果香具有巧克力复杂度，未单独量化其生成。')+a('焦糖气味','conditional','少于烤蒜泥，不等于相对新鲜蒜头减少。'),
    conditions='书述约 60°C 的湿热环境陈放 4—6 周；湿度值及蒜头品种未给。',mechanism='书中明确说黑蒜不是发酵产物，以梅纳反应解释；3-甲基丁醛与复杂巧克力气味联系。',names=['大蒜','黑蒜泥'])
add(55,'熟制（方式未说明）','change','橙色果肉番薯','烹熟橙肉番薯','书述橙肉中的 β-胡萝卜素在烹调时转化为花卉紫罗兰相关分子。',a('花卉气味','emerge'),mechanism='书中 β-胡萝卜素转化机制描述；没有产率测值。',names=['番薯','橙肉番薯'])
add(58,'桶陈/熟成','condition_dependency','不同木桶条件的干邑白兰地','通赛桶与利穆赞桶比较','桶材影响香气和口感；书述通赛桶偏柔和单宁、辛辣椰子，利穆赞偏较强单宁、烟熏香草。',a('椰子气味、香料气味、烟熏气味、香草气味','conditional','方向取决于桶材，不是随时间单向变化。')+o('单宁口感','conditional','不同桶材的比较，未明确感官量表。'))
add(59,'桶陈/熟成','change','书中未限定初始酒龄的干邑','轩尼诗 XO 长期桶陈','果香酯类成熟形成熟果调，桶陈带来椰子气味。',a('熟水果气味、椰子气味','emerge'),names=['轩尼诗XO干邑白兰地','干邑白兰地'],limitations='品牌样本不能代表所有 XO 酒。')
add(60,'切碎/破碎','change','完整新鲜香菇','切开香菇','切开破坏细胞壁，触发反应，使菇味相关 1-辛烯-3-醇增加。',c('1-辛烯-3-醇','increase')+a('蘑菇气味','increase'),mechanism='书中细胞破坏后反应机制；成熟菌褶是另一条件。')
add(61,'干燥','change','新鲜香菇','干香菇','干香菇中菇味分子比例更大，气味更强，另有洋葱化合物与额外草本气味。',a('蘑菇气味','increase')+a('洋葱气味、草本气味','emerge'),names=['香菇','干香菇'],limitations='比例变大不等于每克干重绝对浓度已测量。')
add(63,'干燥','state_profile','基线未报告','桂皮干燥树皮','书中干桂皮样品相对锡兰肉桂具较多坚果、木质和酚类烟熏调。',a('坚果气味、木质气味、烟熏气味、杏仁气味、干草气味'),limitations='跨物种比较，不能把差异归因于干燥。')
add(68,'麦芽处理、发酵','condition_dependency','配方与工艺未固定的皮尔森啤酒','不同啤酒花、麦芽处理和发酵条件','啤酒花决定部分青绿、花香、水果与柑橘；麦芽处理和发酵形成其他风味。',a('青绿气味、花卉气味、水果气味、柑橘气味、焦糖气味、烘烤气味、爆米花气味、乳酪气味'),limitations='多个原料和工艺共同变化，未给每一道工艺的独立效应。')
add(70,'熟制（方式未说明）','change','生姜','烹熟姜','烹煮使姜辣素转为姜酮，带辛甜风味，辣感较低。',c('姜酮','emerge')+o('辣感','decrease')+a('辛甜气味','emerge'),mechanism='书中姜辣素向姜酮转化的描述。',names=['姜','生姜','熟姜'])
add(71,'干燥','change','生姜','干姜','干燥时姜辣素转成姜烯酚，书述干姜更辛辣。',c('姜烯酚','emerge')+o('辣感','increase'),names=['姜','生姜','干姜'],limitations='两倍只针对姜烯酚相对姜辣素分子，不是任意干姜粉对生姜的整体倍数。')
add(74,'水煮','condition_dependency','龙虾尾原料','水煮龙虾尾','烹调产生肉、坚果、爆米花、马铃薯和天竺葵相关香气。',a('肉气味、坚果气味、爆米花气味、熟马铃薯气味、花卉气味'),
    mechanism='书中提及脂肪氧化等反应；更高温的梅纳与史崔克反应属于一般机制讨论。',names=['龙虾尾','水煮龙虾尾'],limitations='不把一般更高温机制当作本条水煮样品实际温度或反应速率。')
add(75,'水煮','change','未烹调角虾','水煮角虾','烹调增加 2-乙酰基-1-吡咯啉浓度；与水煮龙虾的差异作为另一比较关系保留。',c('2-乙酰基-1-吡咯啉','increase')+a('爆米花气味','conditional','书中把该化合物与爆米花调联系，未给感官强度增幅。'),names=['角虾','水煮角虾'],limitations='肉味和马铃薯分子较少是相对龙虾，不能当作角虾煮前后减少。')
add(76,'水煮','change','面包蟹肉原料','水煮面包蟹肉','烹调形成果香酯类；成品还有肉、坚果、爆米花、马铃薯和青绿调。',c('果香酯类','emerge')+a('肉气味、坚果气味、爆米花气味、熟马铃薯气味、青绿气味'),names=['面包蟹肉','水煮面包蟹肉'])
add(79,'成熟/采收','condition_dependency','不同成熟度的葡萄','白苏维浓葡萄酒','原料葡萄成熟度影响酒的青草、水果、甜和酸特征。',a('青草气味、水果气味')+t('甜味、酸味'),limitations='原料成熟度条件，不是酒自身放置后的成熟效应。')
add(83,'熟制（方式未说明）','change','生番茄','煮熟番茄或番茄泥','二甲基硫出现，带来硫调及熟甘蓝关联。',c('二甲基硫','emerge')+a('硫气味、熟甘蓝气味','emerge'),names=['番茄','番茄泥'])
add(84,'冷藏','condition_dependency','书中未明确的番茄比较基线','低于 12°C 贮藏番茄','书称低温抑制关键香气酶，风味流失“高达 65%”。',o('书述总体风味','decrease','上限式书述，未列测定对象、品种、时长，不作通用数值系数。'),conditions='书述低于 12°C；存放时长、湿度、品种、恢复条件和测定法未给。')
add(85,'熬煮/浓缩','change','生番茄','煮稠番茄泥','煮稠后青绿醛减少，焦糖与花卉玫瑰调增加。',c('青绿醛类','decrease')+a('焦糖气味、花卉气味','increase')+a('洋葱气味、丁香气味','conditional'),names=['番茄','番茄泥'])
add(87,'熟成','state_profile','基线未报告','成熟蓝纹乳酪','成熟蓝纹乳酪的二甲基三硫被列为关键香气分子并具洋葱调。',a('洋葱气味、硫气味'),limitations='未给熟成前后浓度差，不能标记含硫分子必然随熟成增加。')
add(89,'熟制（方式未说明）','change','冬南瓜原料','煮熟冬南瓜','β-胡萝卜素在煮熟时转化为 β-紫罗兰酮并带紫罗兰调。',c('β-紫罗兰酮','emerge')+a('花卉气味','emerge'),mechanism='书中给出的前体转化解释，未经独立重现实验。')
add(90,'水煮','state_profile','基线未报告','水煮冬南瓜','水煮冬南瓜的 β-紫罗兰酮被描述为有紫罗兰花香以及热带至浆果的水果气味。',a('花卉气味、水果气味'))
add(91,'储藏','change','采收后较短储藏的橄榄','压榨前延长橄榄储藏','橄榄采收后储藏越久，所得油的醛类与酯类浓度越低。',c('醛类、酯类','decrease'),names=['橄榄','橄榄油'],conditions='储藏对象是压榨前的橄榄；温度、时间与品种未报告。',limitations='不能误用于成品橄榄油相同的时间响应。')
add(96,'混合/乳化','change','较粗分散的特级初榨橄榄油油醋酱','机械搅拌细化的油醋酱','书称机械搅拌越细，多酚释放越多，油醋酱更苦。',c('释放的多酚','increase')+t('苦味','increase'),names=['橄榄油','油醋酱'],mechanism='书中将机械分散、苦味多酚释放与苦感联系。')
add(99,'发酵','condition_dependency','湿热发酵条件（比较基线）','干燥凉爽条件发酵酸种裸麦面包','书述干凉环境对应较多醋酸、偏酸。',c('醋酸','increase')+t('酸味','increase'),conditions='定性干燥、凉爽条件；未给温度、湿度、菌群。',suffix='cool')
add(99,'发酵','condition_dependency','干燥凉爽发酵条件（比较基线）','湿热条件发酵酸种裸麦面包','书述湿热环境对应较多乳酸和更浓果香。',c('乳酸','increase')+a('水果气味','increase'),conditions='定性湿热条件；未给温度、湿度、菌群。',suffix='warm')
add(100,'储藏','condition_dependency','酸种裸麦面包柔软内层','腐坏条件下的面包内层','内层以不饱和醛为主，腐坏时脂质氧化并出现异味。',a('氧化异味','emerge'),mechanism='书中指出脂质氧化。',limitations='只记录缺陷形成条件，不作腐坏食材使用建议。')
add(101,'干燥、发酵','condition_dependency','未固定配方的啤酒','干啤酒花与发酵的兰比克啤酒','干啤酒花关联乳酪、橡木，发酵可能形成香蕉果香，麦芽带枫糖麦芽气味。',a('乳酪气味、木质气味、香蕉气味、花卉气味、枫糖气味、麦芽气味'),limitations='原料和工艺共同变化，非单因素实验。')
add(102,'干燥、发酵','state_profile','基线未报告','使用干啤酒花的兰比克啤酒','相对 IPA，书述兰比克苦韵和啤酒花香较少。',t('苦味')+a('啤酒花气味'),limitations='跨啤酒种类比较，不能把差异全部归因于啤酒花干燥。')
add(106,'煎炒','change','牛排原料','嫩煎牛排','嫩煎促使不饱和醛和其他风味成分形成；工艺影响分子种类及浓度。',c('不饱和醛','emerge','书中描述嫩煎促进形成；未声明其浓度一定高于炉烤。'),names=['牛排','牛肉'],suffix='pan')
add(106,'烘烤','condition_dependency','嫩煎牛排（比较基线）','炉烤牛排','炉烤相对嫩煎形成较多烘烤、坚果相关分子。',c('烘烤气味相关化合物、坚果气味相关化合物','increase'),names=['牛排','牛肉'],suffix='oven')
add(108,'炖煮','change','生鸡胸肉','清炖鸡胸肉','清炖使黄瓜型青绿气味增加、青草减少，并形成蘑菇与洋葱调。',a('黄瓜气味','increase')+a('青草气味','decrease')+a('蘑菇气味、洋葱气味','emerge'))
add(109,'煎炒','state_profile','基线未报告','煎培根（与煎猪排比较）','书述煎培根醛类比煎猪排“少四倍”，部分含氮、含氧挥发物种类更多。',c('醛类、含氮挥发物、含氧挥发物'),limitations='比较基线为另一食材煎猪排；“少四倍”保留原意，不换算为 0.25 倍。',values=[{'attribute':'醛类相对描述','originalText':'比猪排少四倍','unit':'书中相对用语','denominator':'煎猪排；未给测定法','numericTransferAllowed':False}])
add(110,'煎炒','state_profile','基线未报告','煎培根的坚果联系','煎培根的坚果气味分子与澳洲胡桃、核桃、榛果、栗子和花生形成香气联系。',a('坚果气味'))
add(111,'熟制（方式未说明）','condition_dependency','未限定物种与烹调条件的肉类','烹调肉类的化学类别表','表列醛、吡嗪及含硫化合物的可能气味描述。',a('青绿气味、脂肪气味、水果气味、坚果气味、烘烤气味、泥土气味、熟马铃薯气味、爆米花气味、肉气味、洋葱气味'),limitations='通用化学家族映射，不代表每块肉均生成所有分子。')
add(113,'切削、生用/少处理','condition_dependency','阿尔巴白松露','生削与减少香气散失','书述白松露香气浓烈、复杂而易散失，常生削使用。',o('香气持续时间','conditional','香气易挥发；未给加工前后或不同温度的比较量。'),names=['松露','阿尔巴白松露'],limitations='用法与挥发性信息，未将文本化学转化说法当作确定反应式。')
add(116,'水煮、烘烤','state_profile','基线未报告','熟马铃薯','甲硫基丙醛被列为熟马铃薯特征影响化合物。',a('熟马铃薯气味'),limitations='本条没有量化证明水煮与烘烤的强弱差异。')
add(117,'烘烤','change','马铃薯原料','烘烤马铃薯','梅纳反应带来吡嗪及泥土坚果、奶油烘烤马铃薯调。',c('吡嗪类','emerge')+a('泥土气味、坚果气味、奶油气味、烘烤气味','emerge'),mechanism='书中梅纳反应描述；化学名校正记录在原证据。')
add(118,'油炸','change','马铃薯原料','热油油炸薯条','油炸增加甲硫基丙醛、强化熟马铃薯调，并形成烘烤和焦糖气味。',c('甲硫基丙醛','increase')+a('熟马铃薯气味','increase')+a('烘烤气味、焦糖气味','emerge'),names=['马铃薯','薯条'])
add(119,'熟成','change','新鲜山羊乳酪','酶促熟成山羊乳酪','新鲜山羊乳酪较细致；酶促熟成改变风味及质地。',o('总体风味','change')+x('质地','change'),mechanism='书中酶促熟成描述。',limitations='没有为具体香气类别或软硬程度给方向。')
add(122,'成熟/采收','condition_dependency','不同成熟度的蓝莓','采收时状态固定的蓝莓','书述蓝莓品质与风味由采收成熟度决定，摘采后不再改变。',o('采收后风味','conditional','这是书中概括，未独立验证蓝莓生理，也不是统计不显著的实验结果。'),limitations='不可标记成所有储藏条件下“无显著变化”。')
add(125,'干燥、保色处理','condition_dependency','使用二氧化硫保色的干杏桃（比较基线）','未加二氧化硫的干杏桃','未保色处理的干杏桃褐色、有煮熟感，干肉有嚼劲。',color('褐色','conditional')+a('煮熟气味','conditional')+x('嚼劲','conditional'),limitations='比较涉及干燥与保色两条件，不是干燥单因素数值效应。')
add(127,'溶剂接触','change','开花期茉莉花蕾','溶剂接触后的花蕾','书称花蕾接触溶剂后停止释放；开花期与吲哚出现相关。',o('花蕾香气释放','decrease','书中“停止释放”的定性说法，溶剂种类未列。'),conditions='Jasminum sambac；书述开花 24 小时；接触溶剂类型及实验条件未说明。',values=[{'attribute':'书述开花时长','value':24,'unit':'hours','denominator':'Jasminum sambac 的书中描述，非加工设定'}],limitations='不推广至所有茉莉种类，也不把 24 小时当通用萃取时间。')
add(130,'蒸馏、配方混合','condition_dependency','植物原料配方未固定','伦敦干琴酒','蒸馏植物配方中的杜松、香菜籽、欧白芷与鸢尾根提供不同香气联系。',a('松木气味、花卉气味、柑橘气味、樟脑气味、泥土气味、木质气味、香料气味'),limitations='原料来源与配方关系，不是蒸馏前后各类别增加的证据。')
add(131,'配方混合','condition_dependency','伦敦干琴酒（比较基线）','使用更多根原料的普利茅斯琴酒','更多根原料的风格相对更泥土、柑橘与花卉，松木和杜松较少。',a('泥土气味、柑橘气味、花卉气味','increase')+a('松木气味、杜松气味','decrease'),limitations='风格配方比较，未控制各原料浓度及蒸馏工艺。')
add(132,'成熟/采收、腌制','condition_dependency','绿橄榄（比较基线）','成熟黑橄榄','书述成熟黑橄榄草本坚果较少、不那么酸涩、质地较软；成熟与腌制共同影响结果。',a('草本气味、坚果气味','decrease')+t('酸味','decrease')+o('涩感','decrease')+x('硬度','decrease'),names=['黑橄榄','绿橄榄'],limitations='没有分离成熟与腌制方法的独立贡献。')
add(133,'碱液腌制','condition_dependency','盐水或水腌橄榄（比较基线）','快速碱液腌橄榄','快速碱液法的成品较少味。',o('总体风味','decrease'),suffix='alkali')
add(133,'盐水/水腌制','condition_dependency','快速碱液腌橄榄（比较基线）','较久盐水或水腌橄榄','较久的盐水或水腌法保留较浓果香。',a('水果气味','increase','相对碱液腌制；不代表超过鲜果原有浓度。'),suffix='brine')
add(134,'干盐腌制','change','过熟橄榄','干盐腌橄榄','干盐腌制使外观皱缩并有强盐味；香草增香属于另加配方。',t('咸味','emerge')+x('皱缩','emerge'),limitations='芳草不是每个干盐腌样品的必需原料。')
add(135,'盐水/水腌制、发酵、成熟/采收','condition_dependency','未完全成熟的皮夸尔橄榄','成熟后传统盐水发酵皮夸尔黑橄榄','成熟后青绿调减少，成品有复杂脂肪、蔬菜、水果及硫味腌制调。',a('青绿气味','decrease','书述与成熟相联，未单独归因于发酵。')+a('脂肪气味、熟马铃薯气味、桃子气味、硫气味'),names=['黑橄榄','皮夸尔黑橄榄'])
add(140,'水煮','change','生甜菜','水煮甜菜','甜度增强、水果减弱，焦糖与香草增加，另有麦芽、柑橘及香料气味。',t('甜味','increase')+a('水果气味','decrease')+a('焦糖气味、香草气味','increase')+a('麦芽气味、柑橘气味、香料气味'),names=['甜菜','水煮甜菜'])
add(141,'烘烤','change','生甜菜','烘烤甜菜','烘烤出现面包样麦芽调、泥土渐弱，水果和柑橘增加，并产生新青绿分子。',a('烘烤气味、麦芽气味','emerge')+a('泥土气味','decrease')+a('水果气味、柑橘气味','increase')+c('青绿气味相关化合物','emerge'),names=['甜菜','烘烤甜菜'])
add(142,'油炸','change','甜菜薄片','油炸甜菜脆片','甜菜吸收热油中的青绿香气分子，并增强烘烤调。',c('来自食用油的青绿香气分子','increase')+a('烘烤气味','increase'),names=['甜菜','甜菜脆片'],limitations='结果依赖用油种类及状态，不能记作甜菜独有分子。')
add(143,'榨汁','state_profile','基线未报告','石榴汁','石榴汁总体气味较弱，仍有泥土、木质松木、花卉、青绿及马铃薯调。',a('泥土气味、木质气味、松木气味、花卉气味、青绿气味、熟马铃薯气味'),limitations='本条未说明榨汁造成香气减弱。')
add(145,'干煎','change','孜然籽','烹用前略干煎孜然籽','书中以略干煎释放更完整风味。',o('香气释放','increase'),limitations='没有逐分子测量或感官增幅。')
add(147,'水煮','change','生胡萝卜','水煮胡萝卜','萜烯显著减少，β-紫罗兰酮和紫罗兰花香增加；另有 2-壬烯醛的青绿脂肪调。',c('萜烯','decrease')+c('β-紫罗兰酮','increase')+a('花卉气味','increase')+a('青绿脂肪气味'),names=['胡萝卜','生胡萝卜','水煮胡萝卜'])
add(148,'成熟/采收','condition_dependency','不同采收阶段的胡萝卜','早采与大个成熟胡萝卜','早采脆度较佳，成熟获得风味；过大根中心可能更硬、更苦。',x('脆度、硬度')+t('苦味')+o('总体风味'),limitations='属于原料采收条件，未提供连续成熟度响应曲线。')
add(152,'桶陈/熟成','change','白朗姆酒或未限定初始酒龄','木桶熟成朗姆酒','木材挥发物进入酒中，伴随氧化、颜色与香气复杂度变化。',c('木材挥发物','increase')+color('颜色','change')+o('香气复杂度','increase'),mechanism='木材物质迁移与氧化；另加焦糖调色或过滤是酒款附加工序。',limitations='不能把所有颜色变化归因于熟成年限。')
add(155,'发酵','state_profile','基线未报告','韩国发酵大酱','大酱有乳酪、焦糖、花卉、酚类风味与厚实质地；书中比日本味噌深沉复杂。',a('乳酪气味、焦糖气味、花卉气味、酚气味')+x('厚实质地'),limitations='跨产品比较不等于发酵前后变化。')
add(156,'熟成','change','较短时间熟成韩国大酱','延长熟成的大酱','熟成越久，颜色越深、风味更强。',color('颜色深度','increase')+o('总体风味','increase'),limitations='无时间—强度曲线，不同商用配方不可直接等价。')
add(158,'水煮','change','木薯根原料','长时间水煮木薯根','长时间煮后轮廓偏向青绿蜡感和水果椰子气味。',a('青绿蜡气味、椰子气味','change'),conditions='书述长时间水煮，具体时长与温度未给。',limitations='本条为风味记录，不用于推断木薯处理的食品安全充分性。')
add(159,'成熟/采收','change','未成熟大蕉','成熟大蕉','成熟时淀粉转为糖，果皮转黑，风味温和带甜咸。',c('淀粉','decrease')+c('糖','increase')+color('黑色果皮','emerge')+t('甜味、咸味','conditional','原文成熟状态描述，未给甜咸感逐项变化幅度。'))
add(162,'干燥、火烤/烟熏','condition_dependency','绿豆蔻（跨物种比较）','火烤干燥的黑豆蔻','黑豆蔻的烟熏与火烤干燥有关，但其余柑橘、松木、樟脑差异还涉及物种。',a('烟熏气味','emerge')+a('柑橘气味、松木气味、樟脑气味'),names=['黑豆蔻'],limitations='黑豆蔻 Amomum subulatum 与绿豆蔻 Elettaria cardamomum 不同种，不能作同物种工艺对照。')
add(163,'漂白','change','未漂白豆蔻','漂白白豆蔻','书将漂白白色版本描述为风味较淡。',o('总体风味','decrease'),names=['豆蔻','白豆蔻'])
add(164,'研磨、储藏','change','现磨或完整豆蔻','研磨久置豆蔻粉','粉末特有精油易挥发，现磨风味较完整。',c('精油','decrease'),names=['豆蔻','豆蔻粉'],suffix='storage')
add(164,'研磨、去壳','condition_dependency','去壳籽研磨粉（比较基线）','整豆荚研磨后筛粉','整荚研磨再筛的粉比去壳籽粉较不浓烈。',o('总体风味','decrease'),names=['豆蔻','豆蔻粉'],suffix='hull',limitations='不是因研磨时间增加而风味下降的证据。')
add(166,'熟制（方式未说明）','condition_dependency','白肉桃原料','烹煮白肉桃','白肉桃在烹煮时容易碎，书中较建议生用。',x('结构完整性','decrease'),names=['桃子','白肉桃'],limitations='多汁、香甜与低酸是白肉/黄肉比较，未当作烹煮后的味觉变化。')
add(167,'切削、烘烤、网烤','condition_dependency','黄肉桃原料','切开与适合烤制的黄肉桃','黄肉桃切后较能保持形状，书中认为适合烘烤或网烤。',x('结构完整性','conditional','切后保持形状是状态描述；未报告烤制后硬度变化。'),names=['桃子','黄肉桃'],limitations='适宜加工建议不是效果实验。')
add(171,'烘烤','state_profile','基线未报告','烘烤甜菜图示輪廓','小型香气轮标示木质、青绿、蔬菜、焦糖，细分含泥土与马铃薯。',a('木质气味、青绿气味、蔬菜气味、焦糖气味、泥土气味、熟马铃薯气味'),names=['甜菜','烘烤甜菜'],limitations='仅图示存在性，不把轮图大小转为浓度。')
add(172,'发酵','state_profile','基线未报告','牛奶发酵优格','优格含丁二酮奶油调、丙酮优格奶油调、乙醛水果青苹果调，另有青绿青草。',a('奶油气味、水果气味、青苹果气味、青绿气味、青草气味'),names=['优格','牛奶'])
add(174,'切碎/破碎','change','完整黄瓜','切开黄瓜','细胞破坏触发酶促氧化，形成许多特有黄瓜气味醛类。',c('黄瓜气味醛类','emerge')+a('黄瓜气味','emerge'),mechanism='书述细胞破坏与酶促氧化。')
add(175,'切碎/破碎','state_profile','基线未报告','切开黄瓜的分子轮廓','(E,Z)-2,6-壬二烯醛对应黄瓜气味，(E)-2-壬烯醛对应青绿脂肪气味。',a('黄瓜气味、青绿脂肪气味'))
add(176,'成熟/采收、其他处理（未详述）','condition_dependency','同种 Piper nigrum 的不同采收与加工','黑、白、绿、红胡椒状态分类','同物种在采摘和加工后形成不同胡椒状态，不能当同一风味向量。',o('总体风味','conditional','分类层面的差异，没有逐工艺变化方向。'),names=['胡椒','黑胡椒','白胡椒','绿胡椒','红胡椒'])
add(177,'研磨','change','完整黑胡椒','研磨黑胡椒','研磨使花卉调减少。',a('花卉气味','decrease'),limitations='特利奇里品种的鲜明与复杂是另一个品种条件。')
add(179,'研磨','change','完整白胡椒','研磨白胡椒','丁香香料调增强，花卉与草本增加，部分柑橘松木调被取代。',a('丁香气味、花卉气味、草本气味','increase')+a('柑橘气味、松木气味','decrease'),limitations='丁香“辛辣”属于香气，未自动转换成口腔辣度增加。')
add(180,'浸泡','condition_dependency','流动水浸泡白胡椒（比较基线）','死水浸泡的不良加工条件','不良浸泡可能形成腐烂、乳酪或粪便样异味。',a('腐烂气味、乳酪气味、粪便气味','conditional','书中缺陷风险，非所有浸泡必然产生。'),limitations='分子 OCR 不清，未补造分子名。')
add(181,'熟成、干燥','change','未熟成的伊比利火腿原料','熟成干燥伊比利黑毛猪火腿','熟成产生水果、坚果、肉与柑橘气息，并有苯甲醛、呋喃及支链醛关联。',a('水果气味、坚果气味、肉气味、柑橘气味','emerge')+a('枫糖气味、焦糖气味','conditional'),mechanism='原证据列苯甲醛、呋喃类、2-甲基丁醛、3-甲基丁醛；未给浓度。')
add(182,'熟成','state_profile','基线未报告','12 个月熟成帕玛森','书述年轻 fresco 状态有乳酪与坚果气味。',a('乳酪气味、坚果气味'),conditions='书中所述 12 个月熟成；温度、菌群及批次未给。',values=[{'attribute':'熟成时间','value':12,'unit':'months','denominator':'书中年轻 fresco 状态'}])
add(183,'熟成','condition_dependency','较年轻帕玛森（比较基线）','18 个月熟成帕玛森','书述 18 个月状态牛奶风味更显著。',a('牛奶气味','increase'),conditions='书中所述 18 个月熟成；未给其他工艺控制。',values=[{'attribute':'熟成时间','value':18,'unit':'months','denominator':'书中状态比较'}])
add(184,'熟成','state_profile','基线未报告','22 个月以上熟成帕玛森','该状态具乳酪、麦芽、烘烤、坚果、水果及咸脆颗粒。',a('乳酪气味、麦芽气味、烘烤气味、坚果气味、水果气味')+t('咸味')+x('脆颗粒'),conditions='书述至少 22 个月，银标关联；并非当前法规标准核验。',values=[{'attribute':'熟成时间','minimum':22,'operator':'>=','unit':'months','denominator':'书中状态分类'}])
add(185,'熟成','state_profile','基线未报告','30 个月以上熟成帕玛森','书述超陈 stravecchio 状态有强烈鲜味。',t('鲜味'),conditions='书述至少 30 个月；原氨基酸名称 OCR 未核。',values=[{'attribute':'熟成时间','minimum':30,'operator':'>=','unit':'months','denominator':'书中超陈状态'}])
add(186,'熟成','condition_dependency','不同时间、温度与菌群的帕玛森','熟成帕玛森的化学类别','酸类对应乳酪，吡嗪对应烘烤坚果，酯类对应水果，3-甲基丁醛对应麦芽；条件影响各轮廓。',a('乳酪气味、烘烤气味、坚果气味、水果气味、麦芽气味'))
add(187,'熟成','state_profile','基线未报告','至少 9 个月熟成帕达诺','帕达诺相对帕玛森更鲜奶油、较不咸；这是另一乳酪品种。',a('奶油气味')+t('咸味'),conditions='书述至少 9 个月熟成；跨乳酪品种比较。',values=[{'attribute':'熟成时间','minimum':9,'operator':'>=','unit':'months','denominator':'书中帕达诺状态'}],limitations='不可用作帕玛森缩短熟成后的结果。')
add(189,'成熟/采收、熟成','condition_dependency','不同葡萄成熟度与酒龄','卡本内苏维浓的状态依赖','青涩葡萄含较高甜椒吡嗪，酒龄也需保留；分子与蔬菜甜椒、白胡椒气味联系。',c('甜椒相关吡嗪','conditional','较高浓度对应青涩原料，未给酒龄独立响应。')+a('甜椒气味、白胡椒气味'))
add(190,'发酵、火烤/烟熏','condition_dependency','配方和工艺未固定的香肠原料','西班牙乔利佐香肠','烟熏红椒粉、发酵和脂质分解共同影响烟熏、青绿、甜椒、肉、水果、花卉及内酯香气。',a('烟熏气味、青绿气味、甜椒气味、烘烤气味、肉气味、硫气味、水果气味、花卉气味、桃子气味、椰子气味'),limitations='烟熏可来自配方中红椒粉，不能假设每根香肠直接烟熏。')
add(191,'桶陈/熟成','state_profile','基线未报告','橡木桶陈放肯塔基纯波本','书中样品含水果苹果、丁香、椰子、烟熏与香草气味联系。',a('水果气味、苹果气味、丁香气味、椰子气味、烟熏气味、香草气味'),limitations='没有同酒桶陈前后对照；部分分子标准名尚需核。')
add(192,'桶陈/熟成','condition_dependency','低内酯浓度的波本威士忌','内酯浓度较高的波本威士忌','书述桶内酯低浓度呈甜香与橡木，浓度增高更甜香、更椰子。',a('椰子气味、甜香气味','increase'),limitations='这是浓度依赖，未建立熟成时间→内酯浓度函数；甜香未等同舌上甜味。')
add(194,'萃取','condition_dependency','热萃咖啡（比较基线）','冷萃咖啡','书述冷萃较少烘烤调、较多水果和花香。',a('烘烤气味','decrease')+a('水果气味、花卉气味','increase'),conditions='冷萃与热萃；豆种、烘焙度、粉水比、时间、温度和萃取率未报告。',limitations='不作所有咖啡的冷萃通则。')
add(195,'烘烤','state_profile','基线未报告','烤阿拉比卡咖啡豆图文比例','轮廓烘烤占 65%；烘烤调内的分母另为一般烘烤 30%、咖啡 65%、麦芽 5%；奶油 10% 分母未明。',a('烘烤气味、咖啡气味、麦芽气味、奶油气味'),names=['咖啡','烤阿拉比卡咖啡豆'],limitations='这些是书述轮廓比例，不是质量、浓度或感官强度。')
add(196,'烘烤','state_profile','基线未报告','烤阿拉比卡咖啡豆分子轮廓','2-糠基硫醇对应咖啡香，糠基乙基二硫化物对应甜摩卡，另有香料、水果、柑橘与青绿。',a('咖啡气味、摩卡气味、香料气味、水果气味、柑橘气味、青绿气味'),names=['咖啡','烤阿拉比卡咖啡豆'])
add(197,'加热（方式未说明）、发酵','condition_dependency','大豆与小麦原料','日本酱油制作','加热与发酵共同产生或构成焦糖枫糖、水果、花卉、木质微烟熏与烘烤轮廓。',a('焦糖气味、枫糖气味、水果气味、花卉气味、木质气味、烟熏气味、烘烤气味'),limitations='多步骤工艺未拆出单独贡献。')
add(198,'熟制（方式未说明）','change','已制成日本酱油','再次烹煮日本酱油','再次烹煮使 2-乙酰基-1-吡咯啉、葫芦巴内酯、2-乙基-3,5-二甲基吡嗪及乳酪味酸类增加。',c('2-乙酰基-1-吡咯啉、葫芦巴内酯、2-乙基-3,5-二甲基吡嗪、乳酪味酸类','increase'),limitations='分子方向不可直接等同所有消费者的感官强度方向。')
add(199,'发酵、配方混合','condition_dependency','白菜与调味原料','韩国泡菜','配方和发酵共同影响洋葱、甜椒、柑橘、花卉、烘烤、乳酪及奶油气味。',a('洋葱气味、甜椒气味、柑橘气味、花卉气味、烘烤气味、乳酪气味、奶油气味'),limitations='其他分子名有 OCR 或翻译疑点，未扩大转写。')
add(201,'去皮','condition_dependency','未去皮芝麻籽（比较基线）','去皮芝麻籽','由书中未去皮较苦、较复杂、较脆硬的比较，可表述去皮状态相对更少苦味、较不脆硬。',t('苦味','decrease')+x('脆硬程度','decrease')+o('风味复杂度','decrease'),limitations='方向来自同条相对比较的反向表述，非独立去皮实验。')
add(202,'烘烤','change','生芝麻籽','烤芝麻籽','书以梅纳、焦糖化及史崔克反应解释烘烤、坚果、麦芽、木质、蘑菇、焦糖及蔬菜调形成。',a('烘烤气味、坚果气味、麦芽气味、木质气味、蘑菇气味、焦糖气味、熟马铃薯气味、洋葱气味、蒜气味','emerge'),mechanism='书中梅纳、焦糖化和史崔克反应机制描述。',names=['芝麻籽','烤芝麻籽'],limitations='微甜焦糖属香气描述，没有赋成可量化甜味。')
add(203,'配方混合','change','芝麻酱基底','蜂蜜或糖加入的芝麻哈尔瓦酥糖','复合配方改变芝麻基底轮廓，加入花卉、焦糖枫糖与香草联系。',a('花卉气味、焦糖气味、枫糖气味、香草气味','change')+a('烘烤气味、麦芽气味'),names=['芝麻哈尔瓦酥糖','芝麻酱'],limitations='配方比例未给，不是成分加权气味预测模型。')
add(207,'熬煮/浓缩、发酵、桶陈/熟成','condition_dependency','葡萄汁原料','传统熟成巴萨米克醋','浓缩熬煮、发酵、换桶与熟成形成不同调性，包含醋、焦糖、乳酪及微烟熏。',a('醋气味、焦糖气味、乳酪气味、烟熏气味'),limitations='各步贡献未分别定量；酸气味未自动等同舌上酸度。')
add(208,'水煮','condition_dependency','生四季豆','熟四季豆','书述生熟香气差异不大；仍不能将分子增减设为零。',o('总体香气轮廓','conditional','“差异不大”是书中定性说法，不是有统计功效的无显著差异结论。'),limitations='具体化合物变化另见 E0209。')
add(209,'水煮','change','生四季豆','水煮四季豆','清爽青绿、青草、黄瓜相关分子下降，甲硫基丙醛与熟马铃薯调增加。',c('(Z)-3-己烯醛、(E,Z)-2,6-壬二烯醛、1-戊烯-3-酮','decrease')+c('甲硫基丙醛','increase')+a('青绿气味、青草气味、黄瓜气味','decrease')+a('熟马铃薯气味','increase'))
add(210,'制面、水煮','change','杜兰小麦','制面并烹熟的杜兰意大利面','制作及烹煮后青绿青草醛增加，果香酯和烘烤调减少，醇类在煮水中散失。',c('青绿青草醛类','increase')+c('果香酯类、醇类','decrease')+a('烘烤气味','decrease')+a('花卉气味、香料气味'),mechanism='书述脂肪酸降解、氧化及水中散失；制面与烹煮未分开控制。',names=['杜兰意大利面食','杜兰小麦'])
add(211,'水煮','change','朝鲜蓟原料','水煮朝鲜蓟','烹煮产生烘烤和焦糖味分子，成品还有花卉、水果与柑橘调。',c('烘烤气味相关化合物、焦糖气味相关化合物','emerge')+a('花卉气味、水果气味、柑橘气味'))
add(213,'烘烤','change','生榛果','烤榛果','酮类浓度增加，新吡嗪、呋喃及醛类形成，榛果风味更浓。',c('酮类','increase')+c('吡嗪类、呋喃类、醛类','emerge')+a('榛果气味','increase'),names=['榛果','烤榛果'])
add(214,'成熟/采收','change','未成熟榛果','成熟榛果','未熟多汁酥脆微甜，成熟后更扎实、更具风味。',x('扎实程度','increase')+o('总体风味','increase'),limitations='未量化成熟度或硬度，天然成熟不是烘烤效应。')
add(215,'熟成','change','较早熟成布里乳酪','成熟布里乳酪','蘑菇调在熟成过程中发展，另有乳酪、水煮马铃薯与麦芽轮廓。',a('蘑菇气味','emerge')+a('乳酪气味、熟马铃薯气味、麦芽气味'),limitations='牛奶种类和熟成工艺共同影响样品。')
add(216,'熟成','change','固体布里乳酪','由外向内熟成的布里乳酪','外皮霉菌分解脂肪和蛋白质，使固体逐渐绵密并可流动。',x('流动性','increase')+x('绵密质地','emerge'),mechanism='外皮霉菌酶促分解脂肪与蛋白质。')
add(219,'成熟/采收','change','香蕉未开始表皮褐变状态','表皮开始褐变的香蕉','书中指出此成熟状态挥发性化合物浓度增加。',c('挥发性化合物','increase'),limitations='不意味着所有气味分子均增加，也不提供逐日响应。')
add(220,'干燥','state_profile','基线未报告','香蕉帕萨干香蕉','整条干香蕉具有类似葡萄干的质地。',x('葡萄干样质地'),names=['香蕉','香蕉帕萨'])
add(222,'烘烤','change','生甜杏仁','干烤杏仁','苯甲醛减少，吡嗪、呋喃和吡咯分别关联烘烤坚果、焦糖及爆米花。',c('苯甲醛','decrease')+a('烘烤气味、坚果气味、焦糖气味、爆米花气味','emerge'),limitations='没有原料重量、温度曲线或各分子浓度。')
add(223,'温水处理、去皮','change','带种皮甜杏仁','温水去皮杏仁','温水去皮过程形成蘑菇、熟马铃薯、爆米花调，并有更多焦糖调。',a('蘑菇气味、熟马铃薯气味、爆米花气味','emerge')+a('焦糖气味','increase'),conditions='温水软化褐色种皮后去除；具体温度和时长未给。')
add(224,'萃取','state_profile','基线未报告','苦扁桃来源纯杏仁萃取物','苦扁桃来源萃取物中苯甲醛浓度高。',c('苯甲醛'),names=['杏仁萃取物','苦扁桃'],limitations='与一般食用甜扁桃分列；不从此风味条目推出制备或食用安全。')
add(225,'成熟/采收','change','较未熟梨子','成熟梨子','梨酯随成熟更加显著。',a('梨子气味','increase'),mechanism='书中联系癸二烯酸乙酯；标准分子命名仍需另核。')
add(229,'成熟/采收','state_profile','基线未报告','未成熟酪梨','未熟酪梨呈青绿青草轮廓。',a('青绿气味、青草气味'),limitations='为成熟过程保留初始状态，不标记为加工损失。')
add(230,'成熟/采收','change','未成熟酪梨','成熟酪梨','果香酯类取代部分醛类，香蕉味分子较高并有坚果调。',c('醛类与酯类构成','change')+a('水果气味、香蕉气味、坚果气味','conditional'),limitations='无浓度、成熟度尺度或全品种代表性。')
add(235,'制茶（工序未拆分）','state_profile','基线未报告','中国煎茶','中国煎茶有青绿、甜焦糖、干草与花香；低浓度吲哚对应花香。',a('青绿气味、焦糖气味、干草气味、花卉气味'),names=['茶','中国煎茶'])
add(236,'制茶（工序未拆分）','state_profile','基线未报告','蜜香红茶（大叶乌龙）','书中该制法/品种样品具有柑橘、水果、玫瑰紫罗兰、烘烤、坚果与焦糖调。',a('柑橘气味、水果气味、花卉气味、烘烤气味、坚果气味、焦糖气味'),names=['茶','蜜香红茶（大叶乌龙）'])
add(237,'制茶（工序未拆分）','state_profile','基线未报告','龙井','龙井样品有烘烤、坚果干草、花卉蜂蜜、酚、麦芽和马铃薯调。',a('烘烤气味、坚果气味、干草气味、花卉气味、蜂蜜气味、酚气味、麦芽气味、熟马铃薯气味'),names=['茶','龙井'],limitations='相对其他绿茶的差异不能全部归因于炒制工艺。')
add(238,'制茶（工序未拆分）','state_profile','基线未报告','大吉岭红茶','大吉岭红茶样品具有花卉、蜂蜜、柑橘及桃子椰子内酯气味。',a('花卉气味、蜂蜜气味、柑橘气味、桃子气味、椰子气味'),names=['茶','大吉岭红茶'],limitations='大吉岭是产区，本条仅红茶状态。')
add(240,'成熟/采收、花粉保存','condition_dependency','保留花粉的接骨木花','采摘损失花粉的接骨木花','花粉承载主要独特香味，采摘损失花粉会改变风味。',o('总体风味','change'),limitations='未给花粉损失百分比或具体香气降幅。')
add(243,'制酱、配方混合','condition_dependency','新鲜牡蛎（比较基线）','添加淀粉与糖等制成蚝油','蚝油浓稠、鲜香、复杂鱼味，缺少鲜牡蛎清新蔬菜和海洋调。',x('稠度','increase')+a('鱼气味','change')+a('清新蔬菜气味、海洋气味','decrease')+o('鲜香','conditional','原文“鲜香”未量化拆分为嗅觉和鲜味。'),names=['蚝油','牡蛎'],limitations='复合配方与加工共同影响，不是牡蛎单独加热结果。')
add(248,'冷藏、采后熟化','condition_dependency','采后未熟梨子','约 −1°C 降温启动成熟','书述采后降温是启动成熟程序的条件；此条本身没有具体香气增量。',o('成熟启动','conditional','加工条件记录，不作立即变甜或增香结论。'),conditions='书述约 −1°C；品种、保持时长及后续回温过程未完整列于本条。')
add(249,'熟成','state_profile','基线未报告','卡本内苏维浓新酒','新酒有黑莓、黑醋栗香甜酒、黑樱桃、波森莓、蓝莓与巧克力等描述。',a('浆果气味、巧克力气味'),limitations='原始对象保存各浆果细分类；酒龄未给，不生成时间插值。')
add(250,'熟成','state_profile','基线未报告','卡本内苏维浓老酒','老酒有烟草、松露、雪松木、泥土、铅笔芯与皮革气味。',a('烟草气味、松露气味、木质气味、泥土气味、铅笔芯气味、皮革气味'),limitations='与新酒分列，但没有同批酒时间序列或酒龄年数。')
add(251,'桶陈/熟成','condition_dependency','未固定桶材与陈放条件的卡本内苏维浓','橡木桶陈放卡本内苏维浓','桶材和陈放影响香草、椰子、木质轮廓。',a('香草气味、椰子气味、木质气味'),limitations='非所有卡本内苏维浓酒的固定属性。')
add(252,'制茶（工序未拆分）、酶促氧化','condition_dependency','茶叶原料与产地条件未固定','六类茶的制造与氧化差异','白、绿、黄、乌龙/青、黑、红六类茶的差异来自加工与氧化程度，也受风土采收影响。',o('茶类及总体风味','conditional','分类证据，没有逐工艺的分子或强度差值。'),limitations='不把酶促氧化一概等同微生物发酵。')

# Explicit exclusions after a full sequential reading of all source evidence.
# These source records remain fully available in the original evidence browser.
exclusion_groups = [
    ([1,2,3,4,6,7,9,11,21,26,28,29,31,32,33,38,40,41,42,44,50,56,57,62,64,65,66,67,69,72,73,77,78,80,81,82,86,88,92,93,94,95,97,98,103,104,105,107,112,114,115,120,121,123,124,126,128,129,136,137,138,139,144,146,149,150,151,153,154,157,160,161,165,168,169,170,173,178,188,193,200,204,205,206,212,217,218,221,226,227,228,231,232,233,234,239,241,242,244,245,246,247,253],
     '此条记录原料、部位、品种/产地、自然样品轮廓、分子关系或感知背景，没有明确加工/储藏作用或需新增索引的处理后状态；完整原条保留在证据库。'),
    ([8], '这是新鲜苹果与熟藜麦的共有香气关系，熟制仅出现在比较对象中；未报告苹果加工，也未提供藜麦加工前后关系。'),
    ([20], '这是牛奶与黑巧克力的跨产品香气比较；没有加工条件或配方用量，不把产品差异归因于某道工艺。'),
    ([34], '这是龙舌兰原料产地/海拔与品牌比较，没有桶陈或其他具体加工条件。'),
]
excluded = {}
for ids, reason in exclusion_groups:
    for n in ids:
        eid = f'E{n:04d}'
        assert eid not in excluded
        excluded[eid] = reason

by_evidence = {}
for record in records:
    for eid in record['source']['evidenceIds']:
        by_evidence.setdefault(eid, []).append(record)
assert not (set(by_evidence) & set(excluded)), sorted(set(by_evidence) & set(excluded))
assert set(EVIDENCE) == set(by_evidence) | set(excluded), sorted(set(EVIDENCE) - set(by_evidence) - set(excluded))
assert len({r['id'] for r in records}) == len(records)
audit = []
for eid, original in EVIDENCE.items():
    if eid in by_evidence:
        rows = by_evidence[eid]
        kinds = sorted({r['recordKind'] for r in rows})
        audit.append(dict(evidenceId=eid, decision='included', recordIds=[r['id'] for r in rows],
                          reason='人工逐条纳入：' + '、'.join({'change':'明确变化','condition_dependency':'工艺或状态条件依赖','state_profile':'明确处理后的静态轮廓'}[k] for k in kinds) + '。' + '；'.join(r['summary'] for r in rows)))
    else:
        audit.append(dict(evidenceId=eid, decision='not_applicable', recordIds=[], reason=excluded[eid]))

for r in records:
    assert r['original'] == EVIDENCE[r['source']['evidenceIds'][0]]
    assert r['effects']
    assert all(f['domain'] in {'aroma','taste','texture','chemical','color','other'} for f in r['effects'])
    assert all(f['direction'] in {'increase','decrease','emerge','change','no_significant_change','conditional'} for f in r['effects'])
    assert all(v is not None for v in [r['before'],r['after'],r['conditions'],r['summary']])

output = dict(
    metadata=dict(title='现有书中证据的加工与风味层', sourceEvidenceCount=len(EVIDENCE),
                  includedEvidenceCount=len(by_evidence), excludedEvidenceCount=len(excluded),
                  processingRecordCount=len(records), recordKinds=dict(Counter(r['recordKind'] for r in records)),
                  scope='逐条审阅已有 253 条提取证据；不是 PDF 全书加工信息的穷尽提取。自然成熟、原料采收、配方和静态处理后轮廓单独标型。',
                  directions='increase/decrease 等仅是书中方向；conditional 也用于明确状态而无基线的数据，不等于零或无显著变化。',
                  indexMeaning='多工艺、多效果和多名称可交叉索引；名称关联便于检索，不意味着不同状态可以数值互换。',
                  numericPolicy='条件数值、轮廓比例、分子比较与质量/浓度/感官强度分开保存；不构造加工增量系数。'),
    records=records, audit=audit,
)
target = STUDIO / 'data/processing-book.json'
target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(output['metadata'], ensure_ascii=False, indent=2))
