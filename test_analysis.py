import unittest
from scripts.features import name, tokens, clean_text


class AnalysisTests(unittest.TestCase):
    def test_titles_and_historical_capitalization(self):
        self.assertEqual(name('Statsminister CARL  BILDT (m)'), 'Carl Bildt')
        self.assertEqual(name('Utbildnings- och integrationsministern Simona Mohamsson (L)'), 'Simona Mohamsson')
        self.assertEqual(name('FÖRSTE VICE TALMANNEN'), 'Talmannen')
        self.assertEqual(name('Fredrik Reinfeldt (M) Replik'), 'Fredrik Reinfeldt')

    def test_swedish_words(self):
        self.assertEqual(tokens('Åtgärder, välfärd och EU-politik!'), ['åtgärder','välfärd','och','eu-politik'])

    def test_word_fields_removed_but_speech_retained(self):
        self.assertEqual(clean_text('Vår politik.\n STYLEREF Kantrubrik \\* MERGEFORMAT Partiledardebatt\nNästa fråga.'), 'Vår politik.\n\nNästa fråga.')


if __name__ == '__main__':
    unittest.main()
