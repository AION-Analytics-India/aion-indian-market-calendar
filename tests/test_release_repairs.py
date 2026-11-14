"""Regression acceptance for CAL-02..CAL-09, beyond the original 42 probes."""
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import pytest
from aion_indian_market_calendar import IndiaMarketCalendar, get_market_phase, is_trading_day, is_settlement_day, store


@pytest.fixture
def cal():
    return IndiaMarketCalendar.from_json(Path(__file__).parents[1] / 'src/aion_indian_market_calendar/data/holidays_2026.json')


@pytest.mark.parametrize('value', ['2026-12-28', '2027-01-26', '2025-12-31'])
@pytest.mark.parametrize('method', ['is_trading_day', 'is_market_open', 'is_continuous_trading', 'get_session', 'next_trading_day'])
def test_every_session_query_refuses_unknown(cal, value, method):
    with pytest.raises(ValueError, match='outside'):
        getattr(cal, method)(value)


def test_next_trading_day_exhausts_known_range(cal):
    with pytest.raises(ValueError, match='outside'):
        cal.next_trading_day('2026-12-25')


@pytest.mark.parametrize('value', [datetime(2026,10,23,22,tzinfo=timezone.utc), '2026-10-23T22:00:00Z', '2026-10-24T03:30:00+05:30'])
def test_date_helpers_normalize_before_extracting(value, cal):
    assert not is_trading_day(value, calendar=cal)
    assert not is_settlement_day(value, calendar=cal)


@pytest.mark.parametrize('clock,phase,continuous', [('09:00','PRE_OPEN',False),('09:14:59','PRE_OPEN',False),('09:15','CONTINUOUS',True),('15:30','CLOSED',False)])
def test_nse_preopen_and_continuous_consistent(cal, clock, phase, continuous):
    at='2026-11-13T'+clock+'+05:30'
    assert get_market_phase(at,'NSE',calendar=cal)==phase
    assert cal.is_continuous_trading(at,market='NSE') is continuous


@pytest.mark.parametrize('day,clock,phase', [('2026-12-04','15:15','CLOSING_AUCTION'),('2026-12-07','15:29:59','CONTINUOUS'),('2026-12-07','15:30','CLOSING_AUCTION'),('2026-12-07','15:40','CLOSED'),('2026-12-07','15:50','POST_CLOSE'),('2026-12-07','16:00','CLOSED')])
def test_december7_effective_date(cal, day, clock, phase):
    at=day+'T'+clock+'+05:30'
    market='NSE_EQUITY_FNO_UNDERLYING'
    assert get_market_phase(at,market,calendar=cal)==phase
    assert cal.is_continuous_trading(at,market=market)==(phase=='CONTINUOUS')


@pytest.mark.parametrize('market,clock,phase', [('NSE','14:10','PRE_OPEN'),('NSE','14:20','MUHURAT_TRADING'),('NSE','15:30','CLOSED'),('NSE_EQUITY_FNO_UNDERLYING','15:15','CLOSING_AUCTION'),('NSE_EQUITY_FNO_UNDERLYING','15:20','CLOSING_AUCTION'),('NSE_EQUITY_FNO_UNDERLYING','15:35','CLOSED'),('NIFTY','14:10','PRE_OPEN'),('NIFTY','14:30','MUHURAT_TRADING'),('NIFTY','15:39:59','MUHURAT_TRADING'),('NIFTY','15:40','CLOSED')])
def test_notified_muhurat_segments(cal, market, clock, phase):
    at='2026-11-08T'+clock+'+05:30'
    assert get_market_phase(at,market,calendar=cal)==phase
    assert cal.is_continuous_trading(at,market=market)==(phase=='MUHURAT_TRADING')


def test_legacy_offline_refresh_never_reaches_http(cal, monkeypatch):
    monkeypatch.setenv('AION_IN_CALENDAR_OFFLINE','1')
    monkeypatch.setattr('aion_indian_market_calendar.calendar.urlopen',lambda *a,**k:pytest.fail('HTTP reached'))
    cal.taxonomy_manifesto_url='https://example.invalid/retired'
    with pytest.warns(DeprecationWarning):
        assert cal.refresh_taxonomy_manifesto(force=True) is False


def test_missing_verified_store_has_no_unverified_bundle_fallback(tmp_path,monkeypatch):
    monkeypatch.setenv('AION_IN_CALENDAR_OFFLINE','1')
    monkeypatch.setattr(store,'BUNDLED_DIR',tmp_path/'missing')
    monkeypatch.setattr(store,'CACHE_DIR',tmp_path/'empty')
    store._state.update(loaded=False,data={},source='none',warned=set())
    with pytest.raises(ValueError,match='No verified'):
        IndiaMarketCalendar()


@pytest.mark.parametrize('fault', ['corrupt','schema','bad_payload','bad_years','bad_hash_type','list_files','missing_metadata','same_version_replacement','interrupted'])
def test_rejected_refresh_retains_valid_generation(tmp_path,monkeypatch,fault):
    bundled=Path(__file__).parents[1]/'src/aion_indian_market_calendar/data'
    monkeypatch.setenv('AION_IN_CALENDAR_OFFLINE','1')
    monkeypatch.setattr(store,'BUNDLED_DIR',bundled)
    monkeypatch.setattr(store,'CACHE_DIR',tmp_path/'cache')
    store._state.update(loaded=False,data={},source='none',warned=set())
    original=IndiaMarketCalendar(); before=original.get_session('2026-11-08',market='NIFTY')
    doc=json.loads((bundled/'manifest.json').read_bytes());doc['last_updated']='2099-01-01T00:00:00+00:00'
    payload=(bundled/'holidays_2026.json').read_bytes()
    if fault=='schema':doc['schema_version']=999
    if fault=='corrupt':payload=b'broken'
    if fault=='bad_payload':
        payload=b'{}';doc['files']['holidays_2026.json']=hashlib.sha256(payload).hexdigest()
    if fault=='bad_years':doc['years']=[{}]
    if fault=='bad_hash_type':doc['files']['holidays_2026.json']={}
    if fault=='list_files':doc['files']=[]
    if fault=='missing_metadata':doc.pop('next_review_date')
    if fault=='same_version_replacement':
        doc['last_updated']=json.loads((bundled/'manifest.json').read_text())['last_updated'];doc['files']['holidays_2026.json']='0'*64
    monkeypatch.delenv('AION_IN_CALENDAR_OFFLINE')
    def fetch(url,timeout=5):
        if url.endswith('manifest.json'):return json.dumps(doc).encode()
        return None if fault=='interrupted' else payload
    monkeypatch.setattr(store,'_fetch',fetch)
    result=store.refresh(force=True)
    assert not store.refresh_succeeded(result), result
    assert original.get_session('2026-11-08',market='NIFTY')==before
    assert not (store.CACHE_DIR/'ACTIVE').exists()
    with pytest.raises(ValueError):original.is_trading_day('2027-01-26')


def test_review_due_is_visible(cal,monkeypatch,tmp_path):
    monkeypatch.setenv('AION_IN_CALENDAR_OFFLINE','1')
    monkeypatch.setattr(store,'BUNDLED_DIR',Path(__file__).parents[1]/'src/aion_indian_market_calendar/data')
    monkeypatch.setattr(store,'CACHE_DIR',tmp_path)
    store._state.update(loaded=False,data={},source='none',warned=set())
    status=store.status()
    assert status['review_due'] is True
    assert status['next_review_date']=='2026-10-01'
    assert status['years']==[2026]


def test_unknown_legacy_nse_fo_special_schedule_refuses():
    cal=IndiaMarketCalendar.from_json(Path(__file__).parent/'fixtures/dataset_2026_11_03/holidays_2026.json')
    with pytest.raises(ValueError,match='special-session schedule is unknown'):
        cal.is_market_open('2026-11-08T14:30:00+05:30',market='NIFTY')


def test_offline_poll_does_not_import_fetcher(monkeypatch):
    from aion_indian_market_calendar.__main__ import cmd_poll
    from argparse import Namespace
    monkeypatch.setenv('AION_IN_CALENDAR_OFFLINE','1')
    monkeypatch.setattr(store,'_fetch',lambda *a:pytest.fail('poll fetched while offline'))
    assert cmd_poll(Namespace())==2


def test_unknown_legacy_muhurat_helper_also_refuses():
    from aion_indian_market_calendar import muhurat_session
    cal=IndiaMarketCalendar.from_json(Path(__file__).parent/'fixtures/dataset_2026_11_03/holidays_2026.json')
    with pytest.raises(ValueError,match='special-session schedule is unknown'):
        muhurat_session('2026-11-08','NIFTY',calendar=cal)


def test_unknown_override_does_not_break_unrelated_muhurat(cal):
    from aion_indian_market_calendar import muhurat_session
    payload=json.loads((Path(__file__).parents[1]/'src/aion_indian_market_calendar/data/holidays_2026.json').read_text())
    event=payload['events'][-1].copy();event['id']='UNRELATED_MUHURAT';event['session_override']=[{'market':'unsupported-market','open':'14:00:00','close':'15:00:00'}]
    payload['events'].append(event)
    obj=IndiaMarketCalendar(_raw=payload)
    assert muhurat_session('2026-11-08','NIFTY',calendar=obj).close.isoformat()=='15:40:00'
