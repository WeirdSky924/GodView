import asyncio
import json
import uuid
import sys
sys.path.insert(0, '.')

PROJECT_ID = '35d82acc-1dc7-4f0d-a7e1-9cf919960f6a'

async def create_outlines():
    from app.config import settings
    import asyncpg

    # 直接使用 asyncpg 连接
    db_url = settings.database_url.replace('+asyncpg', '')
    conn = await asyncpg.connect(db_url)

    try:
        # 清理旧大纲
        await conn.execute("DELETE FROM chapter_outlines WHERE project_id = $1", PROJECT_ID)
        print('已清理旧大纲')

        # 获取表的所有列名
        columns = await conn.fetch("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'chapter_outlines'
        """)
        column_names = [c['column_name'] for c in columns]
        print(f'可用列: {column_names}')

        # 创建3章大纲 - 只使用存在的字段
        outlines = [
            {
                'chapter_number': 1,
                'title': '第1章 觉醒',
                'summary': '林默在下城区被半机械打手追踪，马库斯大祭司在圣殿进行量子祭坛仪式召唤K。林默与K相遇，马库斯揭示科技与信仰融合计划的危害，王浩发送加密信息暗示被欺骗。',
                'scenes': json.dumps([
                    {'scene_number': 1, 'title': '追逃开始', 'scene_type': 'action', 'summary': '林默在下城区被半机械打手追踪', 'location': '下城区贫民窟', 'emotion': '紧张'},
                    {'scene_number': 2, 'title': '圣殿仪式', 'scene_type': 'description', 'summary': '马库斯在圣殿进行量子祭坛仪式', 'location': '巨阵科技圣殿', 'emotion': '神秘'},
                    {'scene_number': 3, 'title': '林默与K相遇', 'scene_type': 'dialogue', 'summary': '林默逃脱后与K相遇', 'location': '废弃大楼', 'emotion': '悬念'},
                    {'scene_number': 4, 'title': '王浩的信息', 'scene_type': 'climax', 'summary': '王浩发送加密信息揭示阴谋', 'location': '林默终端', 'emotion': '震惊'}
                ]),
                'emotion_curve': json.dumps({'start': '紧张', 'middle': '悬疑', 'end': '震惊'}),
                'chapter_goals': json.dumps(['建立世界观', '引出主要角色', '埋下伏笔']),
                'target_word_count': 2500,
                'status': 'approved'
            },
            {
                'chapter_number': 2,
                'title': '第2章 逃脱',
                'summary': '林默和K躲避追兵，进入下城区深处发现被控制的实验体群体。马库斯的计划是利用神经网络控制人类意识。K尝试破解控制信号，林默决定反击。',
                'scenes': json.dumps([
                    {'scene_number': 1, 'title': '轮椅逃脱', 'scene_type': 'action', 'summary': 'K用轮椅载林默躲避追兵', 'location': '下城区巷道', 'emotion': '紧张'},
                    {'scene_number': 2, 'title': '发现实验体', 'scene_type': 'description', 'summary': '发现被控制的实验体群体', 'location': '废弃工厂', 'emotion': '沉重'},
                    {'scene_number': 3, 'title': '了解阴谋', 'scene_type': 'dialogue', 'summary': 'K解释意识控制计划', 'location': '藏身处', 'emotion': '严肃'},
                    {'scene_number': 4, 'title': '结盟决定', 'scene_type': 'climax', 'summary': '林默决定加入反抗', 'location': '藏身处', 'emotion': '坚定'}
                ]),
                'emotion_curve': json.dumps({'start': '紧张', 'middle': '沉重', 'end': '决心'}),
                'chapter_goals': json.dumps(['展现下城区惨状', '揭示计划危害', '建立同盟']),
                'target_word_count': 2500,
                'status': 'approved'
            },
            {
                'chapter_number': 3,
                'title': '第3章 联盟',
                'summary': '林默和K根据王浩的坐标找到反抗组织基地。反抗组织揭示马库斯的真正目的——通过量子祭坛将人类意识上传到神明网络。林默决定加入反抗组织，展开反击。',
                'scenes': json.dumps([
                    {'scene_number': 1, 'title': '寻找坐标', 'scene_type': 'action', 'summary': '根据坐标寻找反抗组织', 'location': '地下通道', 'emotion': '迷茫'},
                    {'scene_number': 2, 'title': '反抗组织', 'scene_type': 'description', 'summary': '遇到反抗组织成员', 'location': '反抗基地', 'emotion': '好奇'},
                    {'scene_number': 3, 'title': '揭示真相', 'scene_type': 'dialogue', 'summary': '反抗组织揭示真正阴谋', 'location': '反抗基地会议室', 'emotion': '震撼'},
                    {'scene_number': 4, 'title': '加入反抗', 'scene_type': 'climax', 'summary': '林默决定加入反抗组织', 'location': '反抗基地', 'emotion': '坚定'}
                ]),
                'emotion_curve': json.dumps({'start': '迷茫', 'middle': '震撼', 'end': '坚定'}),
                'chapter_goals': json.dumps(['引入反抗势力', '明确反派目标', '主角成长']),
                'target_word_count': 2500,
                'status': 'draft'
            }
        ]

        for o in outlines:
            # 构建动态 SQL，只包含存在的列
            cols = ['id', 'project_id', 'chapter_number', 'title', 'summary', 'scenes', 'emotion_curve', 'chapter_goals', 'target_word_count', 'status']
            vals = ['$1', '$2', '$3', '$4', '$5', '$6', '$7', '$8', '$9', '$10']
            params = [str(uuid.uuid4()), PROJECT_ID, o['chapter_number'], o['title'], o['summary'], o['scenes'], o['emotion_curve'], o['chapter_goals'], o['target_word_count'], o['status']]

            sql = f"INSERT INTO chapter_outlines ({', '.join(cols)}) VALUES ({', '.join(vals)})"
            await conn.execute(sql, *params)
            print(f"已创建第{o['chapter_number']}章大纲: {o['title']}")

        print('\n大纲创建完成!')

    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(create_outlines())