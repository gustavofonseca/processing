# coding: utf-8
"""
Este processamento gera uma tabulação com contagens, soma, mediana de alguns
elementos do artigo: total de autores, total de citações, total de páginas
"""

import argparse
import logging
import codecs
import datetime

import utils
import choices

logger = logging.getLogger(__name__)


def _config_logging(logging_level='INFO', logging_file=None):

    allowed_levels = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    logger.setLevel(allowed_levels.get(logging_level, 'INFO'))

    if logging_file:
        hl = logging.FileHandler(logging_file, mode='a')
    else:
        hl = logging.StreamHandler()

    hl.setFormatter(formatter)
    hl.setLevel(allowed_levels.get(logging_level, 'INFO'))

    logger.addHandler(hl)

    return logger


def pages(first, last):

    try:
        pages = int(last)-int(first)
    except:
        pages = 0

    if pages >= 0:
        return pages
    else:
        return 0


class Dumper(object):

    def __init__(self, collection, issns=None, output_file=None):

        self._ratchet = utils.ratchet_server()
        self._articlemeta = utils.articlemeta_server()
        self.collection = collection
        self.issns = issns
        self.output_file = codecs.open(output_file, 'w', encoding='utf-8') if output_file else output_file
        header = []
        header.append(u"extraction date")
        header.append(u"study unit")
        header.append(u"collection")
        header.append(u"ISSN SciELO")
        header.append(u"ISSN\'s")
        header.append(u"title at SciELO")
        header.append(u"title thematic areas")
        for area in choices.THEMATIC_AREAS:
            header.append(u"title is %s" % area.lower())
        header.append(u"title current status")
        header.append(u"document publishing ID (PID SciELO)")
        header.append(u"document publishing year")
        header.append(u"document type")
        header.append(u"authors")
        header.append(u"0 authors")
        header.append(u"1 author")
        header.append(u"2 authors")
        header.append(u"3 authors")
        header.append(u"4 authors")
        header.append(u"5 authors")
        header.append(u"+6 authors")
        header.append(u"pages")
        header.append(u"references")
        self.write(','.join(header))

    def write(self, line):
        if not self.output_file:
            print(line.encode('utf-8'))
        else:
            self.output_file.write('%s\r\n' % line)

    def run(self):
        for item in self.items():
            self.write(item)
        logger.info('Export finished')

    def items(self):

        if not self.issns:
            self.issns = [None]

        for issn in self.issns:
            for data in self._articlemeta.documents(collection=self.collection, issn=issn):
                logger.debug('Reading document: %s' % data.publisher_id)
                yield self.fmt_csv(data)
        
    def fmt_csv(self, data):
        countries = set()

        if data.normalized_affiliations:
            countries = set([i['country'].lower() for i in data.normalized_affiliations if 'country' in i and i['country'] != 'undefined'])

        tot_authors = len(data.authors or [])

        issns = []
        if data.journal.print_issn:
            issns.append(data.journal.print_issn)
        if data.journal.electronic_issn:
            issns.append(data.journal.electronic_issn)

        line = []
        line.append(datetime.datetime.now().isoformat()[0:10])
        line.append(u'documents')
        line.append(data.collection_acronym)
        line.append(data.journal.scielo_issn)
        line.append(u';'.join(issns))
        line.append(data.journal.title)
        line.append(u';'.join(data.journal.subject_areas))
        for area in choices.THEMATIC_AREAS:
            if area.lower() in [i.lower() for i in data.journal.subject_areas]:
                line.append(u'1')
            else:
                line.append(u'0')
        line.append(data.journal.current_status)
        line.append(data.publisher_id)
        line.append(data.publication_date[0:4])
        line.append(data.document_type)
        line.append(unicode(tot_authors))
        line.append(u'1' if tot_authors == 0 else u'0')  # total de autores
        line.append(u'1' if tot_authors == 1 else u'0')  # total de autores
        line.append(u'1' if tot_authors == 2 else u'0')  # total de autores
        line.append(u'1' if tot_authors == 3 else u'0')  # total de autores
        line.append(u'1' if tot_authors == 4 else u'0')  # total de autores
        line.append(u'1' if tot_authors == 5 else u'0')  # total de autores
        line.append(u'1' if tot_authors >= 6 else u'0')  # total de autores
        line.append(unicode(pages(data.start_page, data.end_page))),  # total de páginas
        line.append(unicode(len(data.citations or []))) # total de citações

        joined_line = u','.join([u'"%s"' % i.replace(u'"', u'""') for i in line])

        return joined_line


def main():

    parser = argparse.ArgumentParser(
        description='Dump counts of authors, references and pages distribution by article'
    )

    parser.add_argument(
        'issns',
        nargs='*',
        help='ISSN\'s separated by spaces'
    )

    parser.add_argument(
        '--collection',
        '-c',
        help='Collection Acronym'
    )

    parser.add_argument(
        '--output_file',
        '-r',
        help='File to receive the dumped data'
    )

    parser.add_argument(
        '--logging_file',
        '-o',
        help='Full path to the log file'
    )

    parser.add_argument(
        '--logging_level',
        '-l',
        default='DEBUG',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Logggin level'
    )

    args = parser.parse_args()
    _config_logging(args.logging_level, args.logging_file)
    logger.info('Dumping data for: %s' % args.collection)

    issns = None
    if len(args.issns) > 0:
        issns = utils.ckeck_given_issns(args.issns)

    dumper = Dumper(args.collection, issns, args.output_file)

    dumper.run()
