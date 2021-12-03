# coding: utf-8
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import time,datetime
import requests
import MySQLdb
from multiprocessing import Process, Queue, Value, Array
from threading import Timer

host = ('localhost', 8888)

alertmanager_api_url = 'https://alertmanager.qiyuesuo.com/api/v2/alerts'

db = MySQLdb.connect("127.0.0.1", "root", "rootroot", "alertmanager", charset='utf8')
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
        startsAt = rs[n][0]
        fingerprint = rs[n][1]
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
        if len(data) == 0:
            print('no alert!')
        else:
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
                    statusss = metrics_data['status']['inhibitedBy']
                elif len(metrics_data['status']['silencedBy']) > 0:
                    statusss = metrics_data['status']['silencedBy']
                else:
                    statusss = metrics_data['status']['state']
                updatedAt = metrics_data['updatedAt'].replace('T', ' ').replace('Z', ' ')[0:19]
                # updatedAt = int(time.mktime(time.strptime(updatedAt, "%Y-%m-%d %H:%M:%S")))
                updatedAt = (datetime.datetime.fromtimestamp(int(time.mktime(time.strptime(updatedAt,"%Y-%m-%d %H:%M:%S")))) + datetime.timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
                generatorURL = metrics_data['generatorURL']
                labels = metrics_data['labels']
                bb = str(startsAt) + str(fingerprint)
                alert_new_list.append(bb)
                if bb in Resquest.alert_old_list:
                    print('duplicatued alert!')
                else:
                    insert_sql = 'INSERT INTO alertmanager (description,summary,valuess,fingerprint,startsAt,endsAt,receivers,updatedAt,statusss,generatorURL,labels) VALUES ("%s","%s","%s","%s","%s","%s","%s","%s","%s","%s","%s");' %(description,summary,valuess,fingerprint,startsAt,endsAt,receivers,updatedAt,statusss,generatorURL,labels)
                    # print(insert_sql)
                    sqlDMl(insert_sql, db)

        ##### 修正恢复时间
        # print('alert_new_list:' + str(alert_new_list))
        resolved_list = list(set(Resquest.alert_old_list).difference(set(alert_new_list)))
        if len(resolved_list) == 0:
            print("No new alert!")
        else:
            for bb in resolved_list:
                startsAt = bb[0:19]
                fingerprint = bb[19:36]
                print(startsAt)
                print(fingerprint)
                update_sql = 'update alertmanager set endsAt="%s",statusss="resolved" where startsAt="%s" and fingerprint="%s";' % (endtime, startsAt, fingerprint)
                sqlDMl(update_sql, db)
        Resquest.alert_old_list = alert_new_list





        rsp_code = req.status_code
        self.send_response(rsp_code)
        self.send_header('Content-type', 'application/json')  #处理头部为json格式
        # self.send_header('Content-type', 'text/html; charset=utf-8')  #处理数据为text格式
        self.end_headers()
        # self.wfile.write(json.dumps(data1).encode()) 返回json格式数据
        self.wfile.write(str(data).encode()) #返回text格式数据


def curl_localhost():
    rr = requests.get(url='http://127.0.0.1:8888')
    print(rr.status_code)


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
