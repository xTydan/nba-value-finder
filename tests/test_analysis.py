from app.analysis import GameLog, summarize_recent, teammate_absence_split, expected_value

def test_recent_over_hit_rate():
    logs=[GameLog(str(i),"d",{"pts":v},30,{}) for i,v in enumerate([20,25,19,30,22])]
    assert summarize_recent(logs,"pts",21.5)["hit_rate"] == 0.6

def test_absence_split_shrinks_small_sample():
    logs=[GameLog("1","d1",{"ast":8},30,{"star":"out"}),GameLog("2","d2",{"ast":7},30,{"star":"active"}),GameLog("3","d3",{"ast":6},30,{"star":"active"})]
    x=teammate_absence_split(logs,"ast","star")
    assert x["out_games"] == 1 and x["shrunk_out_per_min"] < x["out_per_min"]

def test_ev():
    assert round(expected_value(.55,2),2)==.10
