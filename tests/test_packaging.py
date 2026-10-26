import importlib.util
from pathlib import Path
import pytest
from unittest.mock import patch


def builder():
    spec=importlib.util.spec_from_file_location('titan_builder',Path(__file__).parents[1]/'packaging/build_engine.py')
    module=importlib.util.module_from_spec(spec)
    with patch("subprocess.run"):
        spec.loader.exec_module(module)
    return module


def test_native_sidecar_names():
    m=builder()
    assert m.binary_name('Windows','AMD64')=='wb-engine-x86_64-pc-windows-msvc'
    assert m.binary_name('Darwin','arm64')=='wb-engine-aarch64-apple-darwin'
    with pytest.raises(ValueError):m.binary_name('Windows','ARM64')

def test_process_probe_never_terminates_current_writer():
    import os
    from titan_wb.projects import process_alive
    assert process_alive(os.getpid()) is True
    assert process_alive(0) is True

def test_chinese_export_is_utf8_with_non_utf8_system_default(tmp_path,monkeypatch):
    import json
    from titan_wb.demo import make_demo
    from titan_wb.analysis import analyze
    from titan_wb.export import export_analysis
    original=Path.write_text
    def locale_write(path,data,encoding=None,errors=None,newline=None):
        return original(path,data,encoding=encoding or 'cp1252',errors=errors,newline=newline)
    monkeypatch.setattr(Path,'write_text',locale_write)
    p=make_demo();p['name']='中文实验'
    export_analysis(p,analyze(p),str(tmp_path/'output'))
    assert json.loads((tmp_path/'output/project.json').read_text(encoding='utf-8'))['name']=='中文实验'
