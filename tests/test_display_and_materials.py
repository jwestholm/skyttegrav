"""Offline tests for the focused V2.5.1 display/material changes."""
import ast
import importlib.util
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('fetch_polyhaven', ROOT/'fetch_polyhaven.py')
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


class TestDisplayAndMaterials(unittest.TestCase):
    def test_window_is_4_by_3(self):
        code = (ROOT/'trench_3d_test.py').read_text()
        tree = ast.parse(code)
        bindings = [node for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(target,ast.Tuple) and [item.id for item in target.elts if isinstance(item,ast.Name)] == ['W','H'] for target in node.targets)]
        self.assertEqual(len(bindings), 1)
        self.assertEqual(ast.literal_eval(bindings[0].value), (800,600))
        self.assertIn('CAMERA_VERTICAL_FOV,ww/hh', code)

    def test_api_file_selection_does_not_mix_maps(self):
        tree = {'Diffuse':{'1k':{'png':{'url':'https://example.com/mud_diff_1k.png'}}},
                'Normal':{'1k':{'png':{'url':'https://example.com/mud_nor_dx_1k.png'}}},
                'nor_gl':{'1k':{'png':{'url':'https://example.com/mud_nor_gl_1k.png'}}}}
        self.assertEqual(fetch.choose(tree,'diff'),'https://example.com/mud_diff_1k.png')
        self.assertEqual(fetch.choose(tree,'nor_gl'),'https://example.com/mud_nor_gl_1k.png')

    def test_download_saves_expected_file_names(self):
        tree = {'diff': {'1k': {'png': {'url':'https://example.com/diff_1k.png'}}},
                'nor_gl': {'1k': {'png': {'url':'https://example.com/nor_gl_1k.png'}}}}
        img = Image.new('RGB',(32,32),(120,90,66)); bio=BytesIO();img.save(bio,format='PNG');png=bio.getvalue()
        def responder(url,timeout=25):
            if 'api.polyhaven.com' in url: return __import__('json').dumps(tree).encode()
            return png
        with tempfile.TemporaryDirectory() as d, mock.patch.object(fetch,'OUT',Path(d)), mock.patch.object(fetch,'ASSETS',('brown_mud',)),mock.patch.object(fetch,'open_url',side_effect=responder):
            self.assertTrue(fetch.fetch_all())
            for kind in fetch.MAPS:
                f=Path(d)/('brown_mud_'+kind+'.png')
                self.assertTrue(f.is_file())
                with Image.open(f) as saved:self.assertEqual(saved.size,(512,512))


if __name__=='__main__': unittest.main()
