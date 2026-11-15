from aion_indian_market_calendar import update_notice as m
import pytest

def test_notification_dedup_and_headless(tmp_path):
    calls=[]
    args=(tmp_path,'aion-indian-market-calendar','1.2.0','1.2.1')
    assert not m.offer(*args,False,lambda _: pytest.fail('not enrolled'))['desktop_requested_ok']
    assert m.offer(*args,True,lambda msg: calls.append(msg) or True)['desktop_requested_ok']
    assert m.offer(*args,True,lambda _: pytest.fail('repeated'))['available']=='1.2.1'
    assert len(calls)==1 and '1.2.0' in calls[0] and 'releases/tag/v1.2.1' in calls[0]
    with pytest.raises(ValueError): m.acknowledge(tmp_path,'1.2.2')
    assert m.acknowledge(tmp_path,'1.2.1')['acknowledged']
    assert m.offer(*args,True,lambda _: pytest.fail('acknowledged'))['acknowledged']
    new=m.offer(*args[:-1],'1.2.2',True,lambda _:False)
    assert not new['acknowledged'] and not new['desktop_requested_ok']
    assert m.read(tmp_path)['upgrade_command'].endswith('==1.2.2')
