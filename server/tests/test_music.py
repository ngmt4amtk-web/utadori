import sys,xml.etree.ElementTree as ET
sys.path.insert(0,".")
from utadori import music
def sc(ns,m=4):return dict(meter=m,tempo=120,key=dict(tonic=2,mode="major"),notes=ns)
def durs(x,bar):
    r=ET.fromstring(x)
    for me in r.iter("measure"):
        assert sum(int(n.find("duration").text) for n in me.iter("note"))==bar,me.get("number")
    return r
def test_bar_fill_and_tie():
    x=music.to_musicxml(sc([dict(on=42,dur=12,p=74,lyric="あ",unsure=True),dict(on=57,dur=3,p=73,lyric="<",unsure=False)]));r=durs(x,48)
    assert x.count('<tie type="start"/>')==1 and "&lt;" in x and 'color="#C62828"' in x and x.count("<lyric")==2
def test_every_position_3():
    for on in range(0,48,3):
        for d in range(3,100,3):durs(music.to_musicxml(sc([dict(on=on,dur=d,p=60)])),48)
def test_meter3():
    for on in range(0,36,3):
        for d in range(3,60,3):durs(music.to_musicxml(sc([dict(on=on,dur=d,p=60)],3)),36)
def test_overlap_clean():
    assert [n["dur"] for n in music.clean([dict(on=0,dur=24,p=60),dict(on=12,dur=12,p=62)])]==[12,12]
def test_spell_all_keys():
    assert music.fifths(dict(tonic=9,mode="minor"))==0 and music.fifths(dict(tonic=2,mode="major"))==2
    for t in range(12):
        for md in ("major","minor"):music.fifths(dict(tonic=t,mode=md))
def test_svg():
    assert "<svg" in music.to_svg(music.to_musicxml(sc([dict(on=0,dur=12,p=62,lyric="ら")])))[0]
def test_validate():
    import pytest
    base=dict(grid=6,notes=[dict(on=0,dur=12,p=60),dict(on=12,dur=6,p=62)]);music.validate(base)
    for bad in ([dict(on=0,dur=12,p=60),dict(on=6,dur=6,p=62)],[dict(on=3,dur=6,p=60)],[dict(on=0,dur=9,p=60)],[dict(on=0,dur=0,p=60)],[dict(on=0,dur=6,p=200)],[dict(on=0.5,dur=6,p=60)]):
        with pytest.raises(ValueError):music.validate(dict(grid=6,notes=bad))
def test_explicit_fifths():
    x=music.to_musicxml(dict(meter=4,tempo=90,key=dict(tonic=3,mode="minor",fifths=-6),notes=[dict(on=0,dur=12,p=63)]))
    assert "<fifths>-6</fifths>" in x and "<step>E</step><alter>-1</alter>" in x
