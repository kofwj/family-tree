import pandas as pd
from helpers import auth_headers, create_member, login

def test_auto_generation_on_creation(client, app_module):
    # 1. 创建一个具有普通编辑者角色的用户并登录
    admin_token = login(client)
    response = client.post("/admin/users", json={
        "username": "editor_fixes_test",
        "password": "EditorPass123!",
        "display_name": "测试编辑者",
        "role": "editor",
        "isActive": True
    }, headers=auth_headers(admin_token))
    assert response.status_code == 200, response.text
    editor_token = login(client, username="editor_fixes_test", password="EditorPass123!")

    # 2. 用管理员先建一个父亲（第2代）
    father = create_member(client, admin_token, name="李老爸", gender="男", generation=2)
    assert father["generation"] == 2

    # 3. 关联该编辑者至其可见分支范围 (绑定 member_id 到父亲，并为该家族分配编辑者角色)
    with app_module.Session(app_module.engine) as session:
        db_user = session.exec(app_module.select(app_module.User).where(app_module.User.username == "editor_fixes_test")).first()
        db_user.member_id = father["id"]
        session.add(db_user)
        role = app_module.UserFamilyRole(user_id=db_user.id, family_id=father["primaryFamilyId"], role="editor")
        session.add(role)
        session.commit()

    # 4. 用编辑者新建成员（不传 generation，传 father_id）
    # 由于编辑者没有 core_relation 权限，generation 字段在后端会被过滤
    child = create_member(client, editor_token, name="李小明", gender="男", father_id=father["id"])
    
    # 验证新成员的世代已被自动推导为 3 代 (2 + 1)
    assert child["generation"] == 3

    # 5. 用编辑者创建一个配偶（不传 generation，传 spouse_ids）
    spouse = create_member(client, editor_token, name="王小华", gender="女", spouse_ids=[child["id"]])
    
    # 验证配偶的世代被自动推导为 3 代 (与配偶一致)
    assert spouse["generation"] == 3

    # 6. 测试数据质量检查对缺失世代的成员报错
    # 手动往数据库里塞一个没有世代的成员
    with app_module.Session(app_module.engine) as session:
        bad_member = app_module.Member(name="无世代成员", gender="男", generation=None, primary_family_id=father["primaryFamilyId"])
        session.add(bad_member)
        session.commit()
    
    # 调用数据质量检查接口
    res_quality = client.get("/admin/data-quality", headers=auth_headers(admin_token))
    assert res_quality.status_code == 200
    quality_issues = res_quality.json()["issues"]
    
    # 查找关于无世代成员的世代缺失报错
    missing_gen_issues = [i for i in quality_issues if i["category"] == "missing_generation"]
    assert len(missing_gen_issues) == 1
    assert missing_gen_issues[0]["memberName"] == "无世代成员"
    assert "缺少世代信息" in missing_gen_issues[0]["message"]


def test_excel_incremental_import_does_not_overwrite_history(client, app_module, tmp_path):
    token = login(client)
    
    # 1. 创建历史成员 A 和 B，并且手工关联 A -> B（A是父，B是子）
    father = create_member(client, token, name="历史父亲", gender="男", generation=1)
    child = create_member(client, token, name="历史子女", gender="男", generation=2, father_id=father["id"])
    
    child_id = child["id"]
    father_id = father["id"]
    
    # 确认初始状态
    with app_module.Session(app_module.engine) as session:
        db_child = session.get(app_module.Member, child_id)
        assert db_child.father_id == father_id
        
    # 2. 创建一个只包含 1 个新成员的 Excel 文件
    df = pd.DataFrame([
        {
            "姓名": "导入新员", "性别": "男", "世代": 3, "字辈": "", "排行序号": "", "排行称谓": "",
            "出生日期": "", "去世日期": "", "出生地": "", "去世地": "", "现居住地": "",
            "配偶": "", "父亲": "", "母亲": ""
        }
    ])
    path = tmp_path / "incremental.xlsx"
    df.to_excel(path, index=False)
    
    # 3. 运行增量导入 (replace=False)
    count = app_module.import_excel(str(path), replace=False)
    assert count == 1
    
    # 4. 验证历史成员的 father_id 没有被覆盖/清空
    with app_module.Session(app_module.engine) as session:
        db_child = session.get(app_module.Member, child_id)
        assert db_child.father_id == father_id  # 保持原样，没有被置空


def test_settings_sync_to_primary_family(client, app_module):
    token = login(client)
    
    # 1. 初始状态下检查主家族的姓氏
    response_fam = client.get("/families", headers=auth_headers(token))
    assert response_fam.status_code == 200
    families = response_fam.json()
    assert len(families) == 1
    primary_fam = families[0]
    assert primary_fam["surname"] == "陈"
    assert primary_fam["name"] == "陈氏宗族"
    
    # 2. 修改系统配置（修改站点标题和姓氏）
    payload = {
        "siteTitle": "李氏家谱测试",
        "familySurname": "李",
        "subtitle": "祖德流芳",
        "coverKicker": "LI CLAN",
        "treeDescription": "这是测试描述",
        "memberVisibleFields": ["name", "gender", "generation"],
        "fieldVisibilityTemplates": {
            "viewer": "public",
            "editor": "archive"
        }
    }
    response_set = client.put("/settings", json=payload, headers=auth_headers(token))
    assert response_set.status_code == 200
    
    # 3. 再次获取家族列表，验证主家族的基本属性已被同步联动更新
    response_fam2 = client.get("/families", headers=auth_headers(token))
    assert response_fam2.status_code == 200
    families2 = response_fam2.json()
    assert len(families2) == 1
    updated_fam = families2[0]
    
    assert updated_fam["surname"] == "李"
    assert updated_fam["name"] == "李氏宗族"
    assert updated_fam["siteTitle"] == "李氏家谱测试"
    assert updated_fam["subtitle"] == "祖德流芳"
    assert updated_fam["coverKicker"] == "LI CLAN"
