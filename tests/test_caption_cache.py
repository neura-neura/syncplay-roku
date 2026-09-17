import os
from bridge.caption_cache import CaptionCache, MAX_AGE, GRACE


def put(folder, number, age, now, size=10):
    p = folder / ('caption-' + f'{number:064x}' + '.png')
    p.write_bytes(b'x'*size)
    os.utime(p, (now-age, now-age))
    return p


def test_expiry_and_unrelated_files(tmp_path):
    now=2_000_000_000
    old=put(tmp_path,1,MAX_AGE+1,now)
    recent=put(tmp_path,2,100,now)
    for name in ['movie.mp4','captions.srt','font.ttf','config.json','caption-not-a-hash.png']:
        (tmp_path/name).write_text('preserve')
    link=tmp_path/('caption-'+'f'*64+'.png');link.symlink_to(tmp_path/'movie.mp4')
    result=CaptionCache(tmp_path).cleanup(now=now)
    assert result['removed']==1 and result['freedBytes']==10
    assert not old.exists() and recent.exists() and link.is_symlink()
    assert len(list(tmp_path.iterdir()))==7


def test_size_evicts_oldest_but_preserves_inflight(tmp_path):
    now=2_000_000_000
    old=put(tmp_path,1,3000,now)
    newer=put(tmp_path,2,2000,now)
    active=put(tmp_path,3,10,now,size=30)
    result=CaptionCache(tmp_path).cleanup(now=now,max_bytes=20)
    assert not old.exists() and not newer.exists() and active.exists()
    assert result['remainingBytes']==30  # Grace may temporarily exceed the target.
    CaptionCache(tmp_path).cleanup(now=now+GRACE,max_bytes=20)
    assert not active.exists()


def test_reuse_refreshes_retention(tmp_path):
    import time
    now=time.time()
    used=put(tmp_path,1,MAX_AGE+100,now)
    cache=CaptionCache(tmp_path);cache.touch(used)
    assert cache.cleanup(now=now+1)['removed']==0
    assert used.exists()
