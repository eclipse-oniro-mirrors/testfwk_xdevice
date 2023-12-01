# xdevice
- [xdevice](#xdevice组件)
  - [简介](#简介)
  - [目录](#目录)
  - [约束](#约束)
  - [使用](#使用)
  - [相关资料](#相关资料)
  - [相关仓](#相关仓)

## 简介
xdevice是OpenHarmony中为测试框架的核心组件，提供用例执行所依赖的相关服务。

xdevice主要包括以下几个主要模块：

- command，用户与测试平台命令行交互模块，提供用户输入命令解析，命令处理。
- config，测试框架配置模块，提供测试平台串口连接方式和USB连接方式的不同配置选项。
- driver，测试用例执行器，提供测试用例分发，执行，结果收集等主要测试步骤定义。
- report，测试报告模块，提供测试结果解析和测试报告生成。
- scheduler，测试框架调度模块，提供不同类型的测试执行器调度的调度功能。
- environment，测试框架的环境配置模块，提供设备发现，设备管理的功能。
- testkit，测试框架工具模块，提供json解析，网络文件挂载等操作。
- resource，测试框架资源模块，提供设备连接配置文件和报告模板定义。


## 目录
```
xdevice
├── config                    # xdevice组件配置
│     ├── user_config.xml     # xdevice环境配置
├── src                       # 组件源码目录
│     ├── xdevice
├── plugins                   # xdevice扩展模块
|     |—— ohos                # openharmony测试驱动插件
│           ├── src           # 扩展模块源码
│           └── setup.py      # ohos扩展模块安装脚本
|     |--devicetest           # devicetest测试驱动插件
|           └── setup.py      # deviectest扩展模块安装脚本
```


## 约束
运行环境要求：

- python版本>=3.7.5
- pyserial>=3.3
- paramiko>=2.7.1
- rsa>=4.0

## 使用
- **安装xdevice**

  1. 打开xdevice安装目录。

  2. 打开控制台，执行如下命令：
    ```
    python setup.py install
    ```

- **安装ohos扩展模块**

  1. 打开plugins\ohos安装目录。

  2. 打开控制台，执行如下命令：
    ```
    python setup.py install
    ```

- **修改user\_config.xml**

    user\_config.xml是框架提供的用户配置文件，用户可以根据自身环境信息配置相关内容，具体介绍如下：

    1. **environment环境相关配置**

       以下列出三种device配置。
    
       ```xml
       <environment>
           <!-- 标准系统设备配置>
           <device type="usb-hdc"> <!-- type: 设备连接方式,usb-hdc表示使用hdc命令控制设备(默认) -->
               <ip></ip> <!-- ip: 远端设备地址,ip和port为空时使用本地设备,非空时使用远端设备 -->
               <port></port> <!-- port: 远端设备端口号 -->
               <sn></sn> <!-- sn: 设备串口号列表,串口号之间用分号;分隔,sn为空时使用所有本地设备,非空时使用指定的sn设备 -->
           </device>
       
           <!-- 轻量系统设备配置(轻量系统设备进行测试时，需要刷入已经集成好测试用例的系统，所以需要配置两个串口进行通信，如设备支持，可以将两个serial标签的com口设置为一致)，可配置多个 -->
           <device type="com" label="wifiiot"> <!-- type: 设备连接方式，com表示连接方式为串口；label：设备种类，如wifiiot -->
               <serial> <!-- serial：表示一个串口定义 -->
                   <com></com> <!-- serial：表示本地连接的串口，如COM4 -->
                   <type>cmd</type> <!-- type：表示串口类型，cmd为命令串口 -->
                   <baud_rate>115200</baud_rate> <!-- baud_rate、data_bits、stop_bits、timeout：为串口波特率等串口参数，一般采用默认值即可 -->
                   <data_bits>8</data_bits>
                   <stop_bits>1</stop_bits>
                   <timeout>20</timeout>
               </serial>
               <serial>
                   <com></com>
                   <type>deploy</type> <!-- type：表示串口类型，cmd为刷机串口 -->
                   <baud_rate>115200</baud_rate>
               </serial>
           </device>
       
           <!-- 小型系统设备配置，可配置多个 -->
           <device type="com" label="ipcamera">
               <serial>
                   <com></com>
                   <type>cmd</type>
                   <baud_rate>115200</baud_rate>
                   <data_bits>8</data_bits>
                   <stop_bits>1</stop_bits>
                   <timeout>1</timeout>
               </serial>
           </device>
           <device type="com" label="ipcamera">
               <ip></ip>
               <port></port>
           </device>
       </environment>
       ```

    2. **测试用例目录设置**
    
       以下为testcase标签内容及作用。
    
       ```xml
       <testcases>
           <!-- dir标签和server标签同时配置时只有一个会起作用 -->
           <!-- 指定测试用例目录，为空则默认设置为当前项目下的testcase文件夹 -->
           <dir></dir>
           <!-- nfs挂载配置，label取值为NfsServer -->
           <server label="NfsServer">
               <ip></ip>   <!-- 挂载环境IP地址 -->
               <port></port>  <!-- 挂载环境端口 -->
               <dir></dir>  <!-- 对应挂载的外部路径 -->
               <username></username>  <!-- 登录用户名(remote为false时，可不填或删除) -->
               <password></password> <!-- 登录密码(remote为false时，可不填或删除) -->
               <remote></remote> <!-- nfs服务器与xDevice执行机不在同一机器时，remote配置为true，否则为false -->
           </server>
       </testcases>
       ```
    
    3. **资源目录设置**
    
       以下为resource标签内容及作用。
    
       ```xml
       <resource>
           <!-- 指定资源目录，为空则默认设置为当前项目下的resource文件夹 -->
           <dir></dir>
           <!-- 下载OpenHarmony官网测试资源 -->
           <web_resource>
                <!-- 是否开启功能，TRUE开启/FALSE不开启，默认配置为FALSE -->
                <enable>FALSE</enable>
                <!-- 下载接口地址 -->
                <url></url>
            </web_resource>>
       </resource>
       ```
    
    4. **日志打印等级设置**
    
       以下为loglevel标签内容及作用。
    
       ```xml
       <!-- 默认为INFO，如需更详细信息可设置为DEBUG -->
       <loglevel>INFO</loglevel>
       ```


-   **选定任务类型**
    
    设备执行的测试支撑套件是由测试配置文件所指定。

    每类XTS测试套都有一个json格式的测试配置文件，主要配置了需要使用的kits(测试支撑套件)等信息，执行预制和清理操作。

    以下为某个测试支撑套件的json配置文件样例。

    ```json
    {
        //测试支撑套件描述
        "description":"Configuration for acecshi Tests",
    
        //指定执行当前测试支撑套件的设备
        //environment设置为可选,如不设置,将从框架中注册的设备中选择一个符合的空闲设备执行用例
        "environment":{
              "type":"device",
              "label":"wifiiot"
        },
    
        //指定设备执行的驱动
        "driver":{
            "type":"OHJSUnitTest",
            "test-timeout":"700000",
            "bundle-name":"com.open.harmony.acetestfive",
            "package-name":"com.open.harmony.acetestfive",
            "shell-timeout":"700000",
        },
    
        //kit的作用是为了支撑测试执行活动
        "kits":[
            {
              "type":"ShellKit",
              "run-command":[
                "remount",
                "mkdir /data/data/resource"
              ],
              "teardown-command":[
                "remount",
                "rm -rf /data/data/resource"
              ]
            }
        ]
    }
    ```


- **启动框架**
  
  可以通过以下几种方式启动框架
  - Linux系统可以运行根目录下的run.sh文件
  - Windows系统可以运行根目录下的run.bat文件
  - Linux和Windows系统皆可运行项目目录下的src\xdevice\\\_\__main___.py文件

- **执行指令**

  框架指令可以分为三组：help、list、run。在指令序列中，以run为最常用的执行指令。

  1. **help**

     输入help指令可以查询框架指令帮助信息。

     ```bash
     help:
         use help to get information.  
     usage:
         run:  Display a list of supported run command.
         list: Display a list of supported device and task record.  
     Examples:
         help run
         help list
     ```

     说明： help run：展示run指令相关说明 help list：展示 list指令相关说明。

  2. **list**

     list指令用来展示设备和相关的任务信息。

     ```bash
     list:
         This command is used to display device list and task record.  
     usage:
           list
           list history
           list <id>  
     Introduction:
         list:         display device list
         list history: display history record of a serial of tasks
         list <id>:    display history record about task what contains specific id  
     Examples:
         list
         list history
         list 6e****90
     ```

     说明： list: 展示设备信息 list history: 展示任务历史信息 list <id>: 展示特定id的任务其历史信息。

  3. **run**

     run指令主要用于执行测试任务。

     ```bash
     run:
         This command is used to execute the selected testcases.
         It includes a series of processes such as use case compilation, execution, and result collection.  
     usage: run [-l TESTLIST [TESTLIST ...] | -tf TESTFILE
                 [TESTFILE ...]] [-tc TESTCASE] [-c CONFIG] [-sn DEVICE_SN]
                 [-rp REPORT_PATH [REPORT_PATH ...]]
                 [-respath RESOURCE_PATH [RESOURCE_PATH ...]]
                 [-tcpath TESTCASES_PATH [TESTCASES_PATH ...]]
                 [-ta TESTARGS [TESTARGS ...]] [-pt]
                 [-env TEST_ENVIRONMENT [TEST_ENVIRONMENT ...]]
                 [-e EXECTYPE] [-t [TESTTYPE [TESTTYPE ...]]]
                 [-td TESTDRIVER] [-tl TESTLEVEL] [-bv BUILD_VARIANT]
                 [-cov COVERAGE] [--retry RETRY] [--session SESSION]
                 [--dryrun] [--reboot-per-module] [--check-device]
                 [--repeat REPEAT]
                 action task  
     Specify tests to run.
       positional arguments:
       action                Specify action
       task                  Specify task name,such as "ssts", "acts", "hits"
     ```

     run常用指令基本使用方式如下。

     | xDevice命令             | 功能                                                         | 示例                                                         |
     | :---------------------- | :----------------------------------------------------------- | :----------------------------------------------------------- |
     | run xts                 | 运行所有指定类型的xts模块，如acts，hits，ssts等              | run acts                                                     |
     | run -l XXX              | 运行指定测试套。如有多个测试套，测试套之间以分号分隔         | run -l ActsWifiServiceTest;ActsLwipTest（testcase目录下的测试套名称） |
     | run -sn                 | 指定运行设备sn号，多个sn号之间以分号分隔                     | run acts -sn 10.11.133.22:12345 <br/> run acts -sn 2222122;22321321 |
     | run -rp                 | 指定报告生成路径，默认报告生成在项目根目录下的reports文件夹，以时间戳或任务id建立子目录 | run acts -rp /XXXX/XXX                                       |
     | run -respath            | 指定测试资源路径，默认为项目根目录下的resource文件夹         | run -respath /XXX/XXX/XXX                                    |
     | run -tcpath             | 指定测试用例路径,默认为项目根目录下的testcases文件夹         | run -tcpath /XXX/XXX/XXX                                     |
     | run - ta                | 指定模块运行参数，可以指定运行测试套中的某个用例，多个用例之间以逗号分隔，目前只支持hits | run hits -ta size:large <br/> run hits -l XXXTest -ta class:XXXX(类名)#XXXXX(方法名) |
     | run --retry             | 重新运行上次失败的测试用例                                   | run --retry --session 2022-12-13-12-21-11(report任务报告目录) |
     | run --reboot-per-module | 执行前先重启设备                                             | run --reboot-per-module -l XXXX                              |


- **查看执行结果**

  框架执行run指令，控制台会输出对应的log打印，还会生成对应的执行结果报告。如果使用了-rp参数指定报告路径，那么报告就会生成在指定的路径下。否则报告会存放在默认目录。

  ```
  当前报告目录（默认目录/指定目录）
      ├── result（模块执行结果存放目录）
      │     ├── <模块名>.xml
      │     ├──  ... ... 
      │      
      ├── log (设备和任务运行log存放目录)
      │     ├── <设备1>.log
      │     ├── ... ...
      │     ├── <任务>.log
      ├── summary_report.html（测试任务可视化报告）
      ├── summary_report.html（测试任务数据化报告）
      ├── detail_report.html（详细执行用例结果可视化报告）
      ├── failures_report.html（失败用例可视化报告，无失败用例时不生成）
      ├── summary.ini（记录测试类型，使用的设备，开始时间和结束时间等信息）
      ├── task_info.record（记录执行命令，失败用例等清单信息）
      ├── XXX.zip（对上述文件进行压缩得到的文件）
      ├── summary_report.hash（对压缩文件进行SHA256加密得到的文件）
      └── ... ...
  ```

## 相关仓

  [测试子系统](https://gitee.com/openharmony/docs/blob/master/zh-cn/readme/%E6%B5%8B%E8%AF%95%E5%AD%90%E7%B3%BB%E7%BB%9F.md)

  **test\_xdevice**

  [test\_developertest](https://gitee.com/openharmony/test_developertest/blob/master/README_zh.md)
