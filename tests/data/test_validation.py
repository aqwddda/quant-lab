import numpy as np
import pandas as pd
import pytest
from src.data.validation import validate_bars


@pytest.mark.parametrize('problem',['duplicate','unsorted','nan','inf','zero','negative','high','low',
    'negative_volume','naive','timezone','numeric_string'])
def test_reject_without_repair(canonical,problem):
    data=canonical.copy()
    if problem=='duplicate':data.loc[1,'timestamp']=data.timestamp.iloc[0]
    elif problem=='unsorted':data=data.iloc[::-1]
    elif problem=='naive':data['timestamp']=data.timestamp.dt.tz_localize(None)
    elif problem=='timezone':data['timestamp']=data.timestamp.dt.tz_convert('Asia/Shanghai')
    elif problem=='numeric_string':data['close']=data.close.astype(str)
    else:
        column,value={'nan':('close',np.nan),'inf':('close',np.inf),'zero':('open',0),
            'negative':('open',-1),'high':('high',1),'low':('low',10000),
            'negative_volume':('volume',-1)}[problem]
        data[column]=data[column].astype(float);data.loc[0,column]=value
    before=data.copy(deep=True)
    with pytest.raises(ValueError):validate_bars(data,'1d')
    pd.testing.assert_frame_equal(data,before)


@pytest.mark.parametrize('column',['timestamp','symbol','open','high','low','close'])
def test_missing_required_column(canonical,column):
    with pytest.raises(ValueError,match='Schema'):validate_bars(canonical.drop(columns=column),'1d')


@pytest.mark.parametrize('symbol',['',' AAPL',None,10])
def test_invalid_symbol(canonical,symbol):
    canonical['symbol']=symbol
    with pytest.raises(ValueError):validate_bars(canonical,'1d')
