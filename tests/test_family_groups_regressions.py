import json

from backend.main import FamilyGroup, Member, SiteSetting, MemberFamilyLink
from tests.helpers import auth_headers, create_member, login


def test_default_family_group_is_created(app_module, client):
    token = login(client)
    response = client.get('/families', headers=auth_headers(token))
    assert response.status_code == 200, response.text
    families = response.json()
    assert len(families) == 1
    family = families[0]
    assert family['name'] == '陈氏宗族'
    assert family['surname'] == '陈'
    assert family['isPrimary'] is True
    assert family['siteTitle'] == '陈氏宗族家谱'


def test_member_defaults_to_primary_family(app_module, client):
    token = login(client)
    member = create_member(client, token, name='主家族成员', gender='男')
    assert member['primaryFamilyId'] is not None
    with app_module.Session(app_module.engine) as session:
        db_member = session.get(Member, member['id'])
        assert db_member.primary_family_id is not None
        family = session.get(FamilyGroup, db_member.primary_family_id)
        assert family is not None
        assert family.is_primary is True


def test_family_tree_filters_by_family(app_module, client):
    token = login(client)
    main_member = create_member(client, token, name='陈主线', gender='男')
    with app_module.Session(app_module.engine) as session:
        extra_family = FamilyGroup(name='王氏家族', surname='王', site_title='王氏家族', cover_kicker='WANG CLAN', subtitle='王氏支系', is_primary=False)
        session.add(extra_family)
        session.commit()
        session.refresh(extra_family)
        outsider = Member(name='王外家', primary_family_id=extra_family.id)
        session.add(outsider)
        session.commit()
        session.refresh(outsider)
    response = client.get(f"/families/{main_member['primaryFamilyId']}/tree", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    tree = response.json()
    member_ids = {node['id'] for node in tree['nodes']}
    assert main_member['id'] in member_ids
    assert outsider.id not in member_ids


def test_person_ancestry_endpoint_exists(app_module, client):
    token = login(client)
    father = create_member(client, token, name='父亲', gender='男')
    mother = create_member(client, token, name='母亲', gender='女')
    child = create_member(client, token, name='孩子', gender='男', father_id=father['id'], mother_id=mother['id'])
    response = client.get(f"/members/{child['id']}/ancestry?mode=four-line&generations=3", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['member']['id'] == child['id']
    assert 'paternal' in data['lines']
    assert 'maternal' in data['lines']


def test_family_tree_includes_linked_members(app_module, client):
    token = login(client)
    with app_module.Session(app_module.engine) as session:
        extra_family = FamilyGroup(name='林氏家族', surname='林', site_title='林氏家谱', cover_kicker='LIN CLAN', subtitle='林氏支系', is_primary=False)
        session.add(extra_family)
        session.commit()
        session.refresh(extra_family)
        extra_family_id = extra_family.id
        
        linked_member = Member(name='林林', primary_family_id=1)
        session.add(linked_member)
        session.commit()
        session.refresh(linked_member)
        linked_member_id = linked_member.id
        
        link = MemberFamilyLink(member_id=linked_member.id, family_id=extra_family.id, relation_type='secondary')
        session.add(link)
        session.commit()
        
    response = client.get(f"/families/{extra_family_id}/tree", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    tree = response.json()
    member_ids = {node['id'] for node in tree['nodes']}
    assert linked_member_id in member_ids


def test_member_inherits_parent_family(app_module, client):
    token = login(client)
    with app_module.Session(app_module.engine) as session:
        extra_family = FamilyGroup(name='林氏家族', surname='林', site_title='林氏家谱', cover_kicker='LIN CLAN', subtitle='林氏支系', is_primary=False)
        session.add(extra_family)
        session.commit()
        session.refresh(extra_family)
        extra_family_id = extra_family.id
        
        parent = Member(name='林林爸爸', primary_family_id=extra_family_id, gender='男')
        session.add(parent)
        session.commit()
        session.refresh(parent)
        parent_id = parent.id
        
    response = client.post('/members', json={
        'name': '林小林',
        'gender': '男',
        'father_id': parent_id
    }, headers=auth_headers(token))
    assert response.status_code == 200, response.text
    child = response.json()
    assert child['primaryFamilyId'] == extra_family_id
