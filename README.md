# alertmanager
收集所有的告警数据到数据库中并展示出来
背景：有个标准的三件套，grafana+prometheus+al;ertmanager，现在告警是发送到钉钉或者邮件上，一条一条的，尤其故障发生的时候，看消息总是不清晰直观，所以想展示一个显示所有告警看板的功能。
使用prometheus自带的ALERT和ALERT_FOR_STATE函数，发现展示效果不佳，于是使用有一个插件，发现也是不太好事。尤其是我们使用了grafana8后，很多插件也不兼容了。
最后决定自己写一个功能出来完成这个设计。
于是想到把所有的数据存到数据库中来展示就可以了。

所以先设计了一个表，见alertmanager.sql，然后写了一个alertmanager.py来获取alertmanager的告警接口数据并存入到mysql中。
软件：
python3,
pip install mysqlclient
mysql 5.7

最后grafana效果如下
![](https://s3.bmp.ovh/imgs/2021/12/b8ab8e29192fb519.png)