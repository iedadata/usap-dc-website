#!/opt/rh/python27/root/usr/bin/python

import psycopg2
import psycopg2.extras
import json
import requests

config = json.loads(open('/web/usap-dc/htdocs/config.json', 'r').read())
config.update(json.loads(open('/web/usap-dc/htdocs/inc/report_config.json', 'r').read()))

api = 'https://api.crossref.org/works?filter=award.number:'
bib_api = 'https://api.crossref.org/works/%s/transform/text/x-bibliography'


def connect_to_db():
    info = config['DATABASE']
    conn = psycopg2.connect(host=info['HOST'],
                            port=info['PORT'],
                            database=info['DATABASE'],
                            user=info['USER_CURATOR'],
                            password=info['PASSWORD_CURATOR'])
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return (conn, cur)


def crossref2ref_text(item):
    # probably not needed - the all publications appear to have a DOI that works with the API
    ref_text = ""
    if item.get('author'):
        for author in item['author']:
            first_names = author['given'].split(' ')
            initials = ""
            for name in first_names:
                initials += "%s." % name[0]

            ref_text += "%s, %s" % (author['family'], initials)

    year = ""
    if item.get('published_online'):
        year = item['published_online']['date-parts'][0][0]
    elif item.get('published_print'):
        year = item['published_print']['date-parts'][0][0]
    elif item.get('created'):
        year = item['created']['date-parts'][0][0]
    
    if year != "":
        ref_text += "(%s). " % year

    if item.get('title'):
        ref_text += " %s." % item['title'][0]

    if item.get('container-title'):
        ref_text += " %s" % item['container-title'][0]

    if item.get('volume'):
        ref_text += ", %s" % item['volume']

    if item.get('issue'):
        ref_text += "(%s)" % item['issue']

    if item.get('page'):
        ref_text += ", %s" % item['page']

    ref_text += "."

    print("*****REF_TEXT GENERATED FROM CROSSREF:\n%s") % ref_text

    return ref_text


def get_crossref_pubs(verbose=False):
    (conn, cur) = connect_to_db()
    query = "SELECT * FROM project_award_map"
    cur.execute(query)
    res = cur.fetchall()
    output = ""
    old_uid = 0

    # for each entry in the project_award map, get the award_id, and look up publications in crossref
    for p in res:
        proj_uid = p['proj_uid']
        award_id = p['award_id']
        if verbose:
            print("AWARD: %s") % award_id
        r = requests.get(api + award_id).json()

        items = r['message']['items']
        # for each publication, see if it has a DOI
        for item in items:
            ref_doi = item.get('DOI')
            if ref_doi and ref_doi != '':
                # use the DOI to get the cite-as text from the x-bibliography API
                bib_url = bib_api % ref_doi
                # print(bib_url)
                r_bib = requests.get(bib_url)
                if r_bib.status_code == 200 and r_bib.content:
                    # split off the DOI in the cite-as string, as we don't need in our ref_text
                    ref_text = r_bib.content.rsplit(' doi', 1)[0]
                else:
                    # if x-bibliography API doesn't return anything, generate ref_text from what we have in crossref
                    ref_text = crossref2ref_text(item)
            else:
                # if no DOI, generate ref_text from what we have in crossref
                ref_text = crossref2ref_text(item)

            # check if publicaton already exists in reference table, using DOI or ref_text
            ref_text = unicode(ref_text, 'utf-8')
            query = "SELECT * FROM reference WHERE doi = '%s' OR ref_text = '%s'" % (ref_doi, ref_text)
            cur.execute(query)
            res2 = cur.fetchall()
            sql = ""
            if len(res2) == 0:
                # If not already in reference table, add to table
                # first generate ref_uid
                ref_uid, old_uid = generate_ref_uid(old_uid)
                sql += "INSERT INTO reference (ref_uid, ref_text, doi, from_crossref) VALUES ('%s', '%s', '%s', 't');\n" % (ref_uid, ref_text, ref_doi)
            else:
                ref_uid = res2[0]['ref_uid']

            # Add to project_ref_map, if not already there
            query = "SELECT COUNT(*) FROM project_ref_map WHERE proj_uid='%s' AND ref_uid='%s'" % (proj_uid, ref_uid)
            cur.execute(query)
            res2 = cur.fetchone()
            if res2['count'] == 0:
                sql += "INSERT INTO project_ref_map (proj_uid, ref_uid) VALUES ('%s', '%s');" % (proj_uid, ref_uid)
            if sql != "":
                if verbose:
                    print(sql)
                cur.execute(sql)
                proj_url = config['PROJECT_LANDING_PAGE'] % proj_uid
                output += """<li><a href="%s">%s</a> %s</li>""" % (proj_url, proj_uid, ref_text)

                if verbose:
                    print("Added reference %s: %s to project %s" % (ref_uid, ref_text, proj_uid))

    cur.execute("COMMIT")
    return output


def generate_ref_uid(old_uid):
    if old_uid == 0:
        (conn, cur) = connect_to_db()
        #first find the highest ref_uid already in the table
        query = "SELECT MAX(ref_uid) FROM reference;"
        cur.execute(query)
        res = cur.fetchall()
        old_uid = int(res[0]['max'].replace('ref_', ''))

    old_uid += 1
    ref_uid = 'ref_%0*d' % (7, old_uid)
    return ref_uid, old_uid


if __name__ == '__main__':
    get_crossref_pubs(verbose=True)
