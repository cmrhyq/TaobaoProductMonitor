# 淘宝商品价格监控

本项目暂时实现的功能如下

- 商品价格降价监控
- 降价邮件通知

## 代码结构说明
```
├── common                          -- 常用代码目录
│   ├── logging_log.py              -- 日志模块代码
│   └── read_conf.py                -- 读取config.ini配置代码
├── database                        -- 数据模块目录
│   └── data.py                     -- 操作数据库模块代码
├── logs                            -- 日志目录
│   └── product_monitor.log         -- 运行日志
├── monitor                         -- 监控模块目录
│   └── taobao.py                   -- 淘宝商品监控代码
├── resource                        -- 资源目录
│   ├── driver                      -- db文件目录
│   │   └── chromedriver.exe        -- selenium的浏览器驱动
│   └── template                    -- 图片目录
│   │   └── ...                     -- 邮件报告模板文件
│   └── config.ini                  -- 核心配置文件
├── sql                             -- 数据库脚本目录
│   ├── product_monitor.sql         -- 初始化脚本代码
├── system                          -- 系统代码目录
│   └── conf.py                     -- 系统配置文件代码
├── task                            -- 任务代码目录
│   └── task.py                     -- 任务调度代码
├── utils                           -- 工具代码目录
│   ├── common.py                   -- 常用工具代码
│   ├── mysql_utils.py              -- mysql工具代码
│   ├── send_email.py               -- 发送邮件代码
│   ├── template.py                 -- 邮件模板工具代码
│   └── time_utils.py               -- 时间工具代码
├── main.py                         -- 程序入口代码
├── README.md                       -- 本文档
└── requirements.txt                -- 运行本程序需要的依赖
```

## 使用方法

### 一、修改配置

- 修改项目目录下的resource/config.ini中的配置

### 二、浏览器driver

- 下载适合的浏览器driver放入项目的resource/driver目录下

### 三、运行sql脚本

- sql脚本中的数据为示例数据，若要监控你需要的产品还请自行再products表中插入数据
- 数据可以根据点击淘宝分享按钮后复制的内容来插入，例如以下内容

### 四、运行程序

- 直接运行main.py方法

```
【淘宝】https://m.tb.cn/h.5zxz3j69cN5go4k?tk=XUymWKIqxIz MF6563 「优衣库女装网眼V领短针织开衫长袖薄外套空调衫2024新款468541」
点击链接直接打开 或者 淘宝搜索直接打开
```

## 存在的问题

- 本程序通过扫描数据库中的商品数据来实现扫描、降价监控等，没有对应的web界面，所以需要手动插入数据，当然也可以自己写一个web端来控制
- 本程序是通过 selenium 来实现的价格监控，没有逆向淘宝的api，所以淘宝的ui的xpath可能会有变动

以上问题会在下一个版本解决



## 免责声明

本项目仅做学习用，请勿将`TaobaoProductMonitor`应用到任何可能会违反法律规定和道德约束的工作中,请友善使用`TaobaoProductMonitor`，遵守蜘蛛协议，不要将`TaobaoProductMonitor`用于任何非法用途。如您选择使用`TaobaoProductMonitor`即代表您遵守此协议，作者不承担任何由于您违反此协议带来任何的法律风险和损失，一切后果由您承担。