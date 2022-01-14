# coding: utf-8
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
#import urllib3
from time import sleep
import time,datetime
import requests
import MySQLdb
import MySQLdb.cursors
from dbutils.pooled_db import PooledDB
import datetime
from multiprocessing import Process, Queue, Value, Array
from threading import Timer

host = ('127.0.0.1', 8888)

alertmanager_api_url = 'http://127.0.0.1:9093/api/v2/alerts'
class DbManager(object):
    def __init__(self, host, port, db_name, user_name, password):
        cmds = ["set names utf8mb4;"]
        conn_args = {'host': host,
                     'port': port,
                     'db': db_name,
                     'user': user_name,
                     'passwd': password,
                     'charset': 'utf8',
                     'cursorclass': MySQLdb.cursors.DictCursor
                     }
        #  初始化时，链接池中至少创建的空闲的链接，0表示不创建,mincached: 5
        #  链接池中最大闲置的链接数(0和None不限制): 20
        self._pool = PooledDB(MySQLdb, mincached=5, maxcached=20, setsession=cmds, **conn_args)

    def connection(self):
        return self._pool.connection()


_db_manager = None


def create_db_manager(host='127.0.0.1', port=3306, dbname='alertmanager', username='alertmanager', password='alertmanager'):
    global _db_manager
    if _db_manager is None:
        _db_manager = DbManager(host, port, dbname, username, password)
    return _db_manager

db = create_db_manager().connection()
# db = MySQLdb.connect("127.0.0.1", "alertmanager", "alertmanager", "alertmanager", charset='utf8')
def sqlSelect(sql, db):
        #include:select
        cr = db.cursor()
        cr.execute(sql)
        rs = cr.fetchall()
        cr.close()
        return rs

def sqlDMl(sql, db):
        #include: create
        cr = db.cursor()
        cr.execute(sql)
        db.commit()
        cr.close()

def query_old_alert():
    alert_old_list = []
    fingerprint_sql = 'select startsAt,fingerprint from alertmanager where statusss="active";'
    rs = sqlSelect(fingerprint_sql, db)
    for n in range(len(rs)):
        startsAt = rs[n]['startsAt']
        fingerprint = rs[n]['fingerprint']
        unit_fs = str(startsAt) + str(fingerprint)
        alert_old_list.append(unit_fs)
    return alert_old_list

class Resquest(BaseHTTPRequestHandler):
    alert_old_list = query_old_alert()
    def do_GET(self):
        alert_new_list = []
        endtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        req = requests.get(url=alertmanager_api_url)
        data = json.loads(req.text)
        if len(data) > 0:
            for i in range(len(data)):
                metrics_data = data[i]
                description = metrics_data['annotations'].get('description', '')
                summary = metrics_data['annotations'].get('summary', '')
                valuess = metrics_data['annotations'].get('value', '')
                fingerprint = metrics_data['fingerprint']
                startsAt = metrics_data['startsAt'].replace('T', ' ').replace('Z', ' ')[0:19]
                # stime = int(time.mktime(time.strptime(startsAt,"%Y-%m-%d %H:%M:%S")))  #转换为时间戳
                startsAt = (datetime.datetime.fromtimestamp(int(time.mktime(time.strptime(startsAt,"%Y-%m-%d %H:%M:%S")))) + datetime.timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
                endsAt = metrics_data['endsAt'].replace('T', ' ').replace('Z', ' ')[0:19]
                # endsAt= int(time.mktime(time.strptime(endsAt, "%Y-%m-%d %H:%M:%S")))
                endsAt = (datetime.datetime.fromtimestamp(int(time.mktime(time.strptime(endsAt,"%Y-%m-%d %H:%M:%S")))) + datetime.timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
                receivers = metrics_data['receivers'][0]['name']
                if len(metrics_data['status']['inhibitedBy']) > 0:
                    statusss = '抑制告警'
                elif len(metrics_data['status']['silencedBy']) > 0:
                    statusss = '静默告警'
                else:
                    statusss = metrics_data['status']['state']
                updatedAt = metrics_data['updatedAt'].replace('T', ' ').replace('Z', ' ')[0:19]
                # updatedAt = int(time.mktime(time.strptime(updatedAt, "%Y-%m-%d %H:%M:%S")))
                updatedAt = (datetime.datetime.fromtimestamp(int(time.mktime(time.strptime(updatedAt, "%Y-%m-%d %H:%M:%S")))) + datetime.timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
                generatorURL = metrics_data['generatorURL']
                labels = metrics_data['labels']
                bb = str(startsAt) + str(fingerprint)
                alert_new_list.append(bb)
                if bb not in Resquest.alert_old_list and statusss not in ['静默告警', '抑制告警']:
                    insert_sql = 'INSERT INTO alertmanager (description,summary,valuess,fingerprint,startsAt,endsAt,receivers,updatedAt,statusss,generatorURL,labels) VALUES ("%s","%s","%s","%s","%s","%s","%s","%s","%s","%s","%s");' %(description,summary,valuess,fingerprint,startsAt,endsAt,receivers,updatedAt,statusss,generatorURL,labels)
                    # print(insert_sql)
                    sqlDMl(insert_sql, db)

        ##### 修正恢复时间
        # print('alert_new_list:' + str(alert_new_list))
        resolved_list = list(set(Resquest.alert_old_list).difference(set(alert_new_list)))
        if len(resolved_list) > 0:
            for bb in resolved_list:
                startsAt = bb[0:19]
                fingerprint = bb[19:36]
                #print(startsAt)
                #print(fingerprint)
                update_sql = 'update alertmanager set endsAt="%s",statusss="resolved" where startsAt="%s" and fingerprint="%s";' % (endtime, startsAt, fingerprint)
                sqlDMl(update_sql, db)
        Resquest.alert_old_list = alert_new_list





        rsp_code = req.status_code
        self.send_response(rsp_code)
        self.send_header('Content-type', 'application/json')  #处理头部为json格式
        # self.send_header('Connection', 'keep-alive')
        # self.send_header('Content-type', 'text/html; charset=utf-8')  #处理数据为text格式
        self.end_headers()
        self.wfile.write(json.dumps(data).encode()) #返回json格式数据
        # self.wfile.write(str(data).encode()) #返回text格式数据
# 定义一个新的长连接，减少time_wait
#def long_conn_localhost():
#    client = requests.Session()
#    headers = {'Connection': 'keep-alive'}
#    while True:
#        url = client.get(url='http://127.0.0.1:8888', headers=headers)
        #print(url.status_code)

# 改用urllib3的长连接
#def long_conn_urllib3_localhost():
#    http = urllib3.PoolManager(num_pools=100, headers={'Connection':'keep-alive'}, maxsize=100, block=True)
#    while True:
#      http.request('GET', 'http://127.0.0.1:8888')
#      sleep(1)

def curl_localhost():
    rr = requests.get(url='http://127.0.0.1:8888/alert')
    return rr.status_code


def loop_func(func, second):
    # 每隔second秒执行func函数
    while True:
        timer = Timer(second, func)
        timer.start()
        timer.join()

def start_server():
    server = HTTPServer(host, Resquest)
    print("Starting server, listen at: %s:%s" % host)
    server.serve_forever()
def start_request():
    loop_func(curl_localhost, 1)


if __name__ == '__main__':
    p1 = Process(target=start_server, )
    p2 = Process(target=start_request, )
    p1.start()
    p2.start()
    p1.join()
    p2.join()
#    p2.terminate()


