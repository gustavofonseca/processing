# coding: utf-8
import os
import thriftpy
import json
import logging
from datetime import date

from articlemeta.client import ThriftClient
from thriftpy.rpc import make_client
from xylose.scielodocument import Article, Journal

LIMIT = 1000

logger = logging.getLogger(__name__)

ratchet_thrift = thriftpy.load(
    os.path.join(os.path.dirname(__file__))+'/ratchet.thrift')

citedby_thrift = thriftpy.load(
    os.path.join(os.path.dirname(__file__))+'/citedby.thrift')

accessstats_thrift = thriftpy.load(
    os.path.join(os.path.dirname(__file__))+'/access_stats.thrift')

publication_stats_thrift = thriftpy.load(
    os.path.join(os.path.dirname(__file__))+'/publication_stats.thrift')


class ServerError(Exception):
    def __init__(self, message=None):
        self.message = message or 'thirftclient: ServerError'

    def __str__(self):
        return repr(self.message)


class AccessStats(object):

    def __init__(self, address, port):
        """
        Cliente thrift para o Access Stats.
        """
        self._address = address
        self._port = port

    @property
    def client(self):

        client = make_client(
            accessstats_thrift.AccessStats,
            self._address,
            self._port
        )
        return client

    def _compute_access_lifetime(self, query_result):

        data = []

        for publication_year in query_result['aggregations']['publication_year']['buckets']:
            for access_year in publication_year['access_year']['buckets']:
                data.append([
                    publication_year['key'],
                    access_year['key'],
                    int(access_year['access_html']['value']),
                    int(access_year['access_abstract']['value']),
                    int(access_year['access_pdf']['value']),
                    int(access_year['access_epdf']['value']),
                    int(access_year['access_total']['value'])
                ])

        return sorted(data)

    def access_lifetime(self, issn, collection, raw=False):

        body = {
            "query": {
                "bool": {
                    "must": [{
                            "match": {
                                "collection": collection
                            }
                        },
                        {
                            "match": {
                                "issn": issn
                            }
                        }
                    ]
                }
            },
            "size": 0,
            "aggs": {
                "publication_year": {
                    "terms": {
                        "field": "publication_year",
                        "size": 0,
                        "order": {
                            "access_total": "desc"
                        }
                  },
                  "aggs": {
                        "access_total": {
                            "sum": {
                                "field": "access_total"
                            }
                        },
                        "access_year": {
                            "terms": {
                                "field": "access_year",
                                "size": 0,
                                "order": {
                                    "access_total": "desc"
                                }
                            },
                            "aggs": {
                                "access_total": {
                                    "sum": {
                                        "field": "access_total"
                                    }
                                },
                                "access_abstract": {
                                    "sum": {
                                        "field": "access_abstract"
                                    }
                                },
                                "access_epdf": {
                                    "sum": {
                                        "field": "access_epdf"
                                    }
                                },
                                "access_html": {
                                    "sum": {
                                        "field": "access_html"
                                    }
                                },
                                "access_pdf": {
                                    "sum": {
                                        "field": "access_pdf"
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        query_parameters = [
            accessstats_thrift.kwargs('size', '0')
        ]

        query_result = json.loads(self.client.search(json.dumps(body), query_parameters))

        computed = self._compute_access_lifetime(query_result)

        return query_result if raw else computed


class PublicationStats(object):

    def __init__(self, address, port):
        """
        Cliente thrift para o PublicationStats.
        """
        self._address = address
        self._port = port

    @property
    def client(self):
        client = make_client(
            publication_stats_thrift.PublicationStats,
            self._address,
            self._port
        )

        return client

    def _compute_documents_languages_by_year(self, query_result, years=0):

        year = date.today().year

        years = {str(i): {'pt': 0, 'en': 0, 'es': 0, 'other': 0} for i in range(year, year-years, -1)}

        for item in query_result['aggregations']['publication_year']['buckets']:
            if not item['key'] in years:
                continue

            langs = {'pt': 0, 'en': 0, 'es': 0, 'other': 0}

            for language in item['languages']['buckets']:
                if language['key'] in langs:
                    langs[language['key']] += language['doc_count']
                else:
                    langs['other'] += language['doc_count']

            years[item['key']] = langs

        return years

    def documents_languages_by_year(self, issn, collection, years=0):

        body = {
            "query": {
                "filtered": {
                    "query": {
                        "bool": {
                            "must": [
                                {
                                    "match": {
                                        "issn": issn
                                    }
                                },
                                {
                                    "match": {
                                        "collection": collection
                                    }
                                }
                            ]
                        }
                    }
                }
            },
            "aggs": {
                "publication_year": {
                    "terms": {
                        "field": "publication_year",
                        "size": years,
                        "order": {
                            "_term": "desc"
                        }
                    },
                    "aggs": {
                        "languages": {
                            "terms": {
                                "field": "languages",
                                "size": 0
                            }
                        }
                    }
                }
            }
        }

        query_parameters = [
            publication_stats_thrift.kwargs('size', '0')
        ]

        query_result = json.loads(self.client.search('article', json.dumps(body), query_parameters))

        return self._compute_documents_languages_by_year(query_result, years=years)

    def _compute_number_of_articles_by_year(self, query_result, years=0):

        if years == 0:
            return query_result['aggregations']['id']['value']

        year = date.today().year

        years = {str(i): 0 for i in range(year, year-years, -1)}

        for item in query_result['aggregations']['publication_year']['buckets']:
            if not item['key'] in years:
                continue

            years[item['key']] = item.get('doc_count', 0)

        return [(k, v) for k, v in sorted(years.items(), reverse=True)]

    def number_of_articles_by_year(self, issn, collection, document_types=None, years=0):

        body = {
            "query": {
                "filtered": {
                    "query": {
                        "bool": {
                            "must": [
                                {
                                    "match": {
                                        "issn": issn
                                    }
                                },
                                {
                                    "match": {
                                        "collection": collection
                                    }
                                }
                            ]
                        }
                    }
                }
            },
            "aggs": {
                "id": {
                    "cardinality": {
                        "field": "id"
                    }
                }
            }
        }

        if document_types:

            body['query']['filtered']['filter'] = {
                "query": {
                    "bool": {
                        "should": []
                    }
                }
            }

            for item in document_types:

                body['query']['filtered']['filter']['query']['bool']['should'].append({
                    "match": {
                        "document_type": item
                    }
                })

        if years != 0:
            body['aggs'] = {
                "publication_year": {
                    "terms": {
                        "field": "publication_year",
                        "size": years,
                        "order": {
                            "_term": 'desc'
                        }
                    },
                    "aggs": {
                        "id": {
                            "cardinality": {
                                "field": "id"
                            }
                        }
                    }
                }
            }

        query_parameters = [
            publication_stats_thrift.kwargs('size', '0')
        ]

        query_result = json.loads(self.client.search('article', json.dumps(body), query_parameters))

        return self._compute_number_of_articles_by_year(query_result, years=years)

    def _compute_number_of_issues_by_year(self, query_result, years=0):

        if years == 0:
            return query_result['aggregations']['issue']['value']

        year = date.today().year

        years = {str(i): 0 for i in range(year, year-years, -1)}

        for item in query_result['aggregations']['publication_year']['buckets']:
            if not item['key'] in years:
                continue
            years[item['key']] = item.get('issue', {}).get('value', 0)

        return [(k, v) for k, v in sorted(years.items(), reverse=True)]

    def number_of_issues_by_year(self, issn, collection, years=0, type=None):
        """
        type: ['regular', 'supplement', 'pressrelease', 'ahead', 'special']
        """

        body = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "match": {
                                "issn": issn
                            }
                        },
                        {
                            "match": {
                                "collection": collection
                            }
                        }
                    ]
                }
            },
            "aggs": {
                "issue": {
                    "cardinality": {
                        "field": "issue"
                    }
                }
            }

        }

        if type:
            body['query']['bool']['must'].append({"match": {"issue_type": type}})

        if years != 0:
            body['aggs'] = {
                "publication_year": {
                    "terms": {
                        "field": "publication_year",
                        "size": years,
                        "order": {
                            "_term": 'desc'
                        }
                    },
                    "aggs": {
                        "issue": {
                            "cardinality": {
                                "field": "issue"
                            }
                        }
                    }
                }
            }

        query_parameters = [
            publication_stats_thrift.kwargs('size', '0')
        ]

        query_result = json.loads(self.client.search(
            'article', json.dumps(body), query_parameters))

        return self._compute_number_of_issues_by_year(
            query_result, years=years)

    def _compute_first_included_document_by_journal(self, query_result):

        if len(query_result.get('hits', {'hits': []}).get('hits', [])) == 0:
            return None

        return query_result['hits']['hits'][0].get('_source', None)

    def first_included_document_by_journal(self, issn, collection):

        body = {
            "query": {
                "filtered": {
                    "query": {
                        "bool": {
                            "must": [
                                {
                                    "match": {
                                        "collection": collection
                                    }
                                },
                                {
                                    "match": {
                                        "issn": issn
                                    }
                                },
                                {
                                    "match": {
                                        "issue_type": "regular"
                                    }
                                }
                            ]
                        }
                    }
                }
            },
            "sort": [
                {
                    "publication_date": {
                        "order": "asc"
                    }
                }
            ]
        }

        query_parameters = [
            publication_stats_thrift.kwargs('size', '1')
        ]

        query_result = json.loads(self.client.search('article', json.dumps(body), query_parameters))

        return self._compute_first_included_document_by_journal(query_result)

    def _compute_last_included_document_by_journal(self, query_result):

        if len(query_result.get('hits', {'hits': []}).get('hits', [])) == 0:
            return None

        return query_result['hits']['hits'][0].get('_source', None)

    def last_included_document_by_journal(self, issn, collection, metaonly=False):

        body = {
            "query": {
                "filtered": {
                    "query": {
                        "bool": {
                            "must": [
                                {
                                    "match": {
                                        "collection": collection
                                    }
                                },
                                {
                                    "match": {
                                        "issn": issn
                                    }
                                },
                                {
                                    "match": {
                                        "issue_type": "regular"
                                    }
                                }
                            ]
                        }
                    },
                    "filter": {
                        "exists": {
                            "field": "publication_date"
                        }
                    }
                }
            },
            "sort": [
                {
                    "publication_date": {
                        "order": "desc"
                    }
                }
            ]
        }

        query_parameters = [
            publication_stats_thrift.kwargs('size', '1')
        ]

        query_result = json.loads(self.client.search('article', json.dumps(body), query_parameters))

        return self._compute_last_included_document_by_journal(query_result)


class Citedby(object):

    def __init__(self, address, port):
        """
        Cliente thrift para o Citedby.
        """
        self._address = address
        self._port = port

    @property
    def client(self):
        client = make_client(
            citedby_thrift.Citedby,
            self._address,
            self._port
        )

        return client

    def citedby_pid(self, code, metaonly=False):
        """
        Metodo que faz a interface com o metodo de mesmo nome na interface
        thrift, atribuindo metaonly default como FALSE.
        """

        data = self.client.citedby_pid(code, metaonly)

        return data

    def citedby_meta(self, title, author_surname, year, metaonly=False):
        """
        Metodo que faz a interface com o metodo de mesmo nome na interface
        thrift, atribuindo metaonly default como FALSE.
        """

        data = self.client.citedby_meta(title, author_surname, year, metaonly)

        return data


class Ratchet(object):

    def __init__(self, address, port):
        """
        Cliente thrift para o Ratchet.
        """
        self._address = address
        self._port = port

    @property
    def client(self):
        client = make_client(
            ratchet_thrift.RatchetStats,
            self._address,
            self._port
        )

        return client

    def document(self, code):

        data = self.client.general(code=code)

        return data


class ArticleMeta(ThriftClient):
    pass
