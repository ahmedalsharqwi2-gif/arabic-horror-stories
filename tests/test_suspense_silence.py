import pytest
from remotion_factory.silence_beats import select_beats

def story(indices):return {'scenes':[{'silence_after':i in indices} for i in range(8)]}
def timing():return {'scenes':[{'start':i*12,'end':(i+1)*12} for i in range(8)]}
def test_missing_performed_pause_fails_instead_of_inserting_silence():
 with pytest.raises(ValueError,match='no measured'):select_beats(story([1]),timing(),[])
def test_measured_pause_is_retained_without_retiming():
 a=select_beats(story([1,6]),timing(),[(23.5,24),(83.4,84)])
 assert [x['measured_quiet_ms'] for x in a]==[500,600]
def test_more_than_three_authored_beats_in_one_minute_fails():
 with pytest.raises(ValueError,match='Too many'):select_beats(story([0,1,2,3]),timing(),[(11.5,12),(23.5,24),(35.5,36),(47.5,48)])
