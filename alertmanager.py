# coding: utf-8
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, time, datetime, urllib3, requests, MySQLdb, MySQLdb.cursors
from time import sleep
from dbutils.pooled_db import PooledDB
from multiprocessing import Process, Queue, Value, Array
from threading import Timer

# 启动服务
host = ('localhost', 8888)

alertmanager_api_url_list = ['https://alertmanager.qiyuesuo.com/api/v2/alerts', 'https://alertmanager-com.qiyuesuo.com/api/v2/alerts', 'https://alertmanager-cn.qiyuesuo.cn/api/v2/alerts', 'https://alertmanager-me.qiyuesuo.me/api/v2/alerts']

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
def sqlSelect(sql, db):
        #include:select
        cr = db.cursor()
        cr.execute(sql)
        rs = cr.fetchall()
        cr.close()
        return rs

def sqlDMl(sql, db):
        #include: create,update,insert,delete,alter
        cr = db.cursor()
        cr.execute(sql)
        db.commit()
        cr.close()

def query_old_alert(url):
    alert_old_list = []
    fingerprint_sql = "select startsAt,fingerprint from alertmanager where alertmanager_api_url='%s' and statusss->'$.state'='active' and receivers<>'Watchdog';" %(url)
    rs = sqlSelect(fingerprint_sql, db)
    for n in range(len(rs)):
        startsAt = rs[n]['startsAt']
        fingerprint = rs[n]['fingerprint']
        unit_fs = str(startsAt) + str(fingerprint)
        alert_old_list.append(unit_fs)
    return alert_old_list

def query_uniq_alert(ss, fp, url):
    fingerprint_sql = "select count(fingerprint) as cc from alertmanager where startsAt='%s' and fingerprint='%s' and alertmanager_api_url='%s';" %(ss,fp,url)
    rs = sqlSelect(fingerprint_sql, db)
    if rs[0]['cc'] > 0:
        ifuniq = True
    else:
        ifuniq = False
    # print("1:" + str(ifuniq))
    return ifuniq

class Resquest(BaseHTTPRequestHandler):
    def alert_old_list(url):
        old_alert = query_old_alert(url)
        return old_alert

    def alert_uniq_result(ss, fp, url):
        result = query_uniq_alert(ss, fp, url)
        return result

    def do_GET(self):
        # logging.info("GET request,\nPath: %s\nHeaders:\n%s\n", str(self.path), str(self.headers))
        endtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        for alertmanager_api_url in alertmanager_api_url_list:
            alert_new_list = []
            old_list_bb = Resquest.alert_old_list(url=alertmanager_api_url)
            req = requests.get(url=alertmanager_api_url)
            data = json.loads(req.text)
            if len(data) > 0:
                for i in range(len(data)):
                    metrics_data = data[i]
                    receivers = metrics_data['receivers'][0]['name']
                    if receivers != "Watchdog":
                        if metrics_data['status']['state'] == 'active':
                            description = metrics_data['annotations'].get('description', '')
                            summary = metrics_data['annotations'].get('summary', '')
                            valuess = metrics_data['annotations'].get('value', '')
                            fingerprint = metrics_data['fingerprint']
                            startsAt = metrics_data['startsAt'].replace('T', ' ').replace('Z', ' ')[0:19]
                            startsAt = (datetime.datetime.fromtimestamp(int(time.mktime(time.strptime(startsAt,"%Y-%m-%d %H:%M:%S")))) + datetime.timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
                            endsAt = metrics_data['endsAt'].replace('T', ' ').replace('Z', ' ')[0:19]
                            endsAt = (datetime.datetime.fromtimestamp(int(time.mktime(time.strptime(endsAt,"%Y-%m-%d %H:%M:%S")))) + datetime.timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
                            statusss = json.dumps(metrics_data['status'])
                            updatedAt = metrics_data['updatedAt'].replace('T', ' ').replace('Z', ' ')[0:19]
                            updatedAt = (datetime.datetime.fromtimestamp(int(time.mktime(time.strptime(updatedAt, "%Y-%m-%d %H:%M:%S")))) + datetime.timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
                            generatorURL = metrics_data['generatorURL']
                            labels = json.dumps(metrics_data['labels'])
                            if alertmanager_api_url == "https://alertmanager-com.qiyuesuo.com/api/v2/alerts":
                                env = "com"
                                namespace = metrics_data['labels'].get('namespace', '')
                                if namespace == 'qiyuesuo-a' or namespace == 'ingress-nginx-a':
                                    area = 'a'
                                elif namespace == 'qiyuesuo-b' or namespace == 'ingress-nginx-b':
                                    area = 'b'
                                else:
                                    area = 'other'
                            elif alertmanager_api_url == "https://alertmanager-cn.qiyuesuo.cn/api/v2/alerts":
                                env = "cn"
                                namespace = metrics_data['labels'].get('namespace', '')
                                if namespace == 'qiyuesuo-a' or namespace == 'ingress-nginx-a':
                                    area = 'a'
                                elif namespace == 'qiyuesuo-b' or namespace == 'ingress-nginx-b':
                                    area = 'b'
                                else:
                                    area = 'other'
                            elif alertmanager_api_url == "https://alertmanager-me.qiyuesuo.me/api/v2/alerts":
                                env = "me"
                                namespace = metrics_data['labels'].get('namespace', '')
                                if namespace == 'qiyuesuo':
                                    area = 'a'
                                else:
                                    area = 'other'
                            else:
                                env = metrics_data['labels'].get('exported_env') or metrics_data['labels'].get('env', 'ops')
                                area = (metrics_data['labels'].get('qys_area') or metrics_data['labels'].get('exported_area') or metrics_data['labels'].get('area', 'other')).lower()

                            # 处理数据库
                            if 'MysqlSlowQueries' in metrics_data['labels'].get('alertname', '') or '数据库 慢' in metrics_data['labels'].get('alertname', ''):
                                category = "数据库慢查询"
                            elif 'MysqlTooManyConnections' in metrics_data['labels'].get('alertname', ''):
                                category = "数据库连接数高"
                            elif '数据库 行锁等待' in metrics_data['labels'].get('alertname', ''):
                                category = "数据库行锁"
                            elif '数据库 内存'  in metrics_data['labels'].get('alertname', ''):
                                category = "数据库内存高"
                            elif '数据库 CPU'  in metrics_data['labels'].get('alertname', ''):
                                category = "数据库CPU高"
                            elif '数据库 磁盘'  in metrics_data['labels'].get('alertname', ''):
                                category = "数据库磁盘高"
                            elif 'MysqlSlave'  in metrics_data['labels'].get('alertname', ''):
                                category = "数据库从库"
                            elif 'MysqlRestarted' in metrics_data['labels'].get('alertname', '') or 'MysqlDown' in metrics_data['labels'].get('alertname', ''):
                                category = "数据库宕机"
                            # 处理redis
                            elif 'Redis 流控' in metrics_data['labels'].get('alertname', ''):
                                category = "Redis超流控"
                            elif 'Redis 带宽' in metrics_data['labels'].get('alertname', ''):
                                category = "Redis带宽高"
                            elif 'Redis CPU' in metrics_data['labels'].get('alertname', ''):
                                category = "RedisCPU高"
                            elif 'Redis 内存' in metrics_data['labels'].get('alertname', ''):
                                category = "Redis内存高"
                            # 处理nginx
                            elif 'Too Many Nginx Writing' in metrics_data['labels'].get('alertname', ''):
                                category = "nginx慢"
                            elif '5xx' in metrics_data['labels'].get('alertname', ''):
                                category = "nginx5xx"
                            elif '4xx' in metrics_data['labels'].get('alertname', ''):
                                category = "nginx4xx"
                            # 处理java
                            elif 'heap space' in metrics_data['labels'].get('alertname', '') or 'old space' in metrics_data['labels'].get('alertname', ''):
                                category = "java内存高"
                            elif 'gc' in metrics_data['labels'].get('alertname', ''):
                                category = "javaFGC"
                            elif 'JDBCPool' in metrics_data['labels'].get('alertname', ''):
                                category = "java连接高/等待"
                            elif 'jvm down' in metrics_data['labels'].get('alertname', ''):
                                category = "java服务宕机"
                            # 处理应用
                            elif 'Pod cpu limits more than 98%' in metrics_data['labels'].get('alertname', ''):
                                category = "应用CPU高"
                            elif 'Pod memory limits more than 98%' in metrics_data['labels'].get('alertname', ''):
                                category = "应用内存高"
                            elif 'threads' in metrics_data['labels'].get('alertname', ''):
                                category = "应用线程忙"
                            # 处理mq
                            elif '非delay类型队列' in metrics_data['labels'].get('alertname', ''):
                                category = "MQ非delay队列"
                            elif '是delay类型队列' in metrics_data['labels'].get('alertname', ''):
                                category = "MQdelay队列"
                            elif 'MQ服务宕机' in metrics_data['labels'].get('alertname', '') or 'RabbitmqNodeNotDistributed' in metrics_data['labels'].get('alertname', '') or 'RabbitmqNodeDown' in metrics_data['labels'].get('alertname', ''):
                                category = "MQ宕机"
                            elif 'RabbitmqOutOfMemory' in metrics_data['labels'].get('alertname', '') or 'RabbitmqMemoryHigh' in metrics_data['labels'].get('alertname', ''):
                                category = "MQ内存高"
                            elif 'RabbitmqTooManyConnections' in metrics_data['labels'].get('alertname', ''):
                                category = "MQ连接数高"
                            elif 'RabbitmqDiskFreeAlarm' in metrics_data['labels'].get('alertname', ''):
                                category = "MQ磁盘高"
                            # 处理URL探针
                            elif 'BlackboxSlow' in metrics_data['labels'].get('alertname', ''):
                                category = "URL慢"
                            elif 'BlackboxProbeHttpFailure' in metrics_data['labels'].get('alertname', ''):
                                category = "URL故障"
                            elif 'BlackboxSsl' in metrics_data['labels'].get('alertname', ''):
                                category = "URLSSL证书"
                            # 处理zookeeper
                            elif 'ZookeeperDown' in metrics_data['labels'].get('alertname', '') or 'ZookeeperNotOk' in metrics_data['labels'].get('alertname', ''):
                                category = "ZK宕机"
                            elif 'ZookeeperMissingLeader' in metrics_data['labels'].get('alertname', '') or 'ZookeeperTooManyLeaders' in metrics_data['labels'].get('alertname', ''):
                                category = "ZKLeader异常"
                            elif 'Zookeeper堆积' in metrics_data['labels'].get('alertname', '') or 'Zookeeper阻塞' in metrics_data['labels'].get('alertname', '') or 'Zookeeper平均响应' in metrics_data['labels'].get('alertname', '') or 'Zookeeper打开文件' in metrics_data['labels'].get('alertname', ''):
                                category = "ZK慢"
                            # 处理obs
                            elif 'OBS存储' in metrics_data['labels'].get('alertname', ''):
                                category = "OBS成功率"
                            elif 'OBS-GET类请求' in metrics_data['labels'].get('alertname', ''):
                                category = "OBS延迟高"
                            # 处理elb
                            elif metrics_data['labels'].get('alertname', '').startswith('ELB '):
                                category = "ELB"
                            # 处理kafka
                            elif metrics_data['labels'].get('alertname', '').startswith('kafka'):
                                category = "KAFKA"
                            # 处理ES
                            elif metrics_data['labels'].get('alertname', '').startswith('ES '):
                                category = "ES"
                            # 处理k8s
                            elif metrics_data['labels'].get('alertname', '').startswith('Prometheus') or metrics_data['labels'].get('alertname', '').startswith('Kube') or metrics_data['labels'].get('alertname', '').startswith('Node'):
                                category = "K8S"
                            # 一律其他
                            else:
                                category = "其他"
                            bb = str(startsAt) + str(fingerprint)
                            alert_new_list.append(bb)
                            ifuniq = Resquest.alert_uniq_result(ss=startsAt, fp=fingerprint, url=alertmanager_api_url)
                            # print("2:" + str(ifuniq))
                            if ifuniq == False:
                                sql_arg = (
                                alertmanager_api_url, description, summary, valuess, fingerprint, startsAt, endsAt,
                                receivers, updatedAt, statusss, generatorURL, labels, env, area, category)
                                insert_sql = "INSERT INTO alertmanager (alertmanager_api_url, description, summary, valuess, fingerprint, startsAt, endsAt, receivers, updatedAt, statusss, generatorURL, labels, env, area, category) VALUES " + str(sql_arg) + ";"
                                sqlDMl(insert_sql, db)
                            else:
                                continue
            ##### 修正恢复时间
            resolved_list = list(set(old_list_bb).difference(set(alert_new_list)))
            if len(resolved_list) > 0:
                for bb in resolved_list:
                    startsAt = bb[0:19]
                    fingerprint = bb[19:36]
                    statusss = json.dumps({"state": "resolved", "silencedBy": [], "inhibitedBy": []})
                    update_sql = "update alertmanager set endsAt='%s',statusss='%s' where startsAt='%s' and fingerprint='%s';" % (endtime, statusss, startsAt, fingerprint)
                    sqlDMl(update_sql, db)
            #Resquest.alert_old_list = alert_new_list
            rsp_code = req.status_code
            # self.send_response(rsp_code)
            # self.send_error(rsp_code)
            self.send_response_only(rsp_code)
            # self.log_error()
            self.send_header('Content-type', 'application/json')  #处理头部为json格式
            # self.send_header('Connection', 'keep-alive')
            # self.send_header('Content-type', 'text/html; charset=utf-8')  #处理数据为text格式
            self.end_headers()
            self.wfile.write(json.dumps(data).encode()) #返回json格式数据
            # self.wfile.write(str(data).encode()) #返回text格式数据
# 定义一个新的长连接，减少time_wait
def long_conn_localhost():
    client = requests.Session()
    headers = {'Connection': 'keep-alive'}
    while True:
        url = client.get(url='http://127.0.0.1:8888', headers=headers)
        return url.status_code

# 改用urllib3的长连接
def long_conn_urllib3_localhost():
    http = urllib3.PoolManager(num_pools=100, headers={'Connection': 'keep-alive'}, maxsize=100, block=True)
    while True:
      http.request('GET', 'http://127.0.0.1:8888')
      sleep(1)

def curl_localhost():
    rr = requests.get(url='http://127.0.0.1:8888')
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
