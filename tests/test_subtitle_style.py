import pytest
from pydantic import ValidationError
from bridge.config import Store, SubtitleStyle


def test_style_persistence_and_validation(tmp_path):
    store = Store(tmp_path)
    token = store.config.token
    store.config.subtitle_style = SubtitleStyle(size=60,bold=True,color='#ffdd33',opacity=20)
    store.save()
    restored = Store(tmp_path)
    assert restored.config.subtitle_style == store.config.subtitle_style
    assert restored.config.token == token
    for value in [dict(size=0),dict(size=201),dict(opacity=-1),dict(opacity=101),dict(color='red')]:
        with pytest.raises(ValidationError):
            SubtitleStyle(**value)
