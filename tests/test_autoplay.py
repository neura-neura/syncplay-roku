from bridge.autoplay import Autoplay

def snapshot():
    return {'room':'movies','connected':True,'ready':True,'target':{'paused':True},
            'users':{'movies':{'Roku':{'isReady':True,'file':{'name':'clip'}},'Noir':{'isReady':False,'file':{'name':'clip'}}}}}

def test_countdown_waits_for_everyone_and_fires_only_once():
    a=Autoplay();s=snapshot();a.arm(True)
    assert not a.tick(True,3,s,True,now=0)
    assert a.remaining is None
    s['users']['movies']['Noir']['isReady']=True
    assert not a.tick(True,3,s,True,now=1)
    assert a.remaining==3
    assert a.tick(True,3,s,True,now=4)
    assert not a.tick(True,3,s,True,now=8)

def test_unready_cancels_countdown_and_missing_media_blocks():
    a=Autoplay();s=snapshot();s['users']['movies']['Noir']['isReady']=True;a.arm(True)
    assert not a.tick(True,3,s,False,now=0)
    assert not a.tick(True,3,s,True,now=0)
    s['users']['movies']['Noir']['isReady']=False
    assert not a.tick(True,3,s,True,now=2)
    assert a.remaining is None
