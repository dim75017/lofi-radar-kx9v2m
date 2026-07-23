import unittest

import enrich_public_artist_contacts as subject


class PublicArtistContactEnrichmentTests(unittest.TestCase):
    def test_only_keeps_explicit_business_email(self):
        page = '<p>Personal: jane@example.org</p><p>For booking: booking@artist.test</p>'
        self.assertEqual(subject.business_emails(page), ['booking@artist.test'])

    def test_enrichment_is_limited_to_strict_verified_artist(self):
        artist_schema = ['soundcharts_uuid', 'name', 'contact_url', 'public_contacts']
        opportunity_schema = ['opportunity_status', 'instrumental_status', 'ai_risk', 'rights_status', 'artists']
        payload = {
            'schemas': {'artists': artist_schema, 'opportunities': opportunity_schema},
            'artists': [['artist-1', 'Quiet Artist', 'https://artist.test/contact', []]],
            'opportunities': [['verified', 'instrumental', 'low', 'self_released', [{'soundcharts_uuid': 'artist-1'}]]],
        }
        old_fetch = subject.fetch_html
        subject.fetch_html = lambda url: '<a href="mailto:contact@artist.test">Business contact</a>'
        try:
            summary = subject.enrich(payload, {'artists': {}}, 10, 4)
        finally:
            subject.fetch_html = old_fetch
        self.assertEqual(summary, {'artists_checked': 1, 'emails_found': 1})
        schema = payload['schemas']['artists']
        row = payload['artists'][0]
        self.assertEqual(row[schema.index('email')], 'contact@artist.test')
        self.assertEqual(row[schema.index('contact_research')]['result'], 'email_found')

    def test_non_verified_artist_is_never_fetched(self):
        artist_schema = ['soundcharts_uuid', 'contact_url', 'public_contacts']
        opportunity_schema = ['opportunity_status', 'instrumental_status', 'ai_risk', 'rights_status', 'artists']
        payload = {
            'schemas': {'artists': artist_schema, 'opportunities': opportunity_schema},
            'artists': [['artist-1', 'https://artist.test/contact', []]],
            'opportunities': [['needs_listen', 'instrumental', 'low', 'self_released', [{'soundcharts_uuid': 'artist-1'}]]],
        }
        self.assertEqual(subject.enrich(payload, {'artists': {}}, 10, 4), {'artists_checked': 0, 'emails_found': 0})


if __name__ == '__main__':
    unittest.main()
