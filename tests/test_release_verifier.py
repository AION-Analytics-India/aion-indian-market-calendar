"""The CI helper fails closed on changed artifacts and unsafe archives."""
import importlib.util
import io,json,tarfile
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('release_verifier',Path(__file__).parents[1]/'scripts/verify_release_artifacts.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_inventory_detects_changed_artifact(tmp_path):
    (tmp_path/'aion_indian_market_calendar-1.8.0-py3-none-any.whl').write_bytes(b'test wheel')
    (tmp_path/'aion_indian_market_calendar-1.8.0.tar.gz').write_bytes(b'test sdist')
    doc=module.inventory(tmp_path,'a'*40);module.validate_inventory(tmp_path,doc,'a'*40)
    (tmp_path/'aion_indian_market_calendar-1.8.0.tar.gz').write_bytes(b'changed')
    with pytest.raises(ValueError):module.validate_inventory(tmp_path,doc,'a'*40)


@pytest.mark.parametrize('name',['../outside','C:/outside','root/..\\outside'])
def test_source_archive_cannot_escape(tmp_path,name):
    p=tmp_path/'bad.tar.gz'
    with tarfile.open(p,'w:gz') as t:
        item=tarfile.TarInfo(name);item.size=1;t.addfile(item,io.BytesIO(b'x'))
    with pytest.raises(ValueError):module.extract_source(p,tmp_path/'extract')
    assert not (tmp_path/'outside').exists()
