"""公開候補schemaとWriterの受理する属性・出所が一致することを検証する。"""
import json,re,unittest
from pathlib import Path
from pedigree_registry import SOURCES

class SchemaContractTest(unittest.TestCase):
    def test_supported_fields_and_source_classes(self):
        schema=json.loads(Path('data/pedigree/schema.json').read_text());fact=schema['$defs']['fact']['properties'];pattern=fact['field']['pattern']
        self.assertEqual(set(fact['source']['properties']['source_class']['enum']),SOURCES)
        for name in ['birth_country','training_country','training_country_matches','training_country_user','training_start_history','sex']:
            self.assertIsNotNone(re.fullmatch(pattern,'attribute:'+name))
        for value in ['parent:S','parent:DS','parent:'+'D'*10]:self.assertIsNotNone(re.fullmatch(pattern,value))
        for value in ['attribute:unknown','parent:X','parent:'+'S'*11,'training_country_user']:
            self.assertIsNone(re.fullmatch(pattern,value))

if __name__=='__main__':unittest.main()
