# run命令
**run命令比较复杂，包含多种选项。框架在解析run命令的组合后，根据命令运行测试套。run命令涉及的选项可分为执行类选项和约束类选项。**

## 1.执行类选项
> 执行选项是与下文约束选项相对的概念。执行选项可以和run命令进行组合，形成一条有效的运行命令，从而将测试套运行起来。约束选项，则用于约束测试套运行时的行为，光有约束选项，执行框架是无法正确运行的。

  - run

    运行所有执行类型的xts测试套，如acts，hits，ssts等

    | 格式 | 使用说明 | 实例 |
    | :--- | :--- | :--- |
    | run xts测试套名 | 运行所有执行类型的测试套 | run acts |

  - run -l 

    运行指定的测试套。长选项为"run --testlist"。后面的之为测试套配置文件列表。命令执行后，框架会在testcases目录下找到对应的"测试套名.json"，然后解析执行。
    如下所示，用户输入 ACtsWifiTest 和 ActLwipTest两个模块，要求框架执行。

    | 格式 | 使用说明 | 实例 |
    | :--- | :--- | :--- |
    | run -l 测试套1;测试套2 | 测试套之间以分号分隔 | run -l ActsWifiTest;ActsLwipTest |

  - run -tf

    指定测试套文件。长选项表示为"run --testfile"。

    如下所示，用户指定了test/resoucre/test.txt文件作为模块选项的来源文件，框架将读取这个文件中的内容，解析后执行。

    | 格式 | 使用说明 | 实例 |
    | :--- | :--- | :--- |
    | run -tf 测试套文本路径 | 用户可以指定一个测试套文件让框架来执行 | run -tf test/resoucre/test.txt |


  - run -tc

    指定测试用例。长选项表示为"run --testcase"。只支持devicetest类型的python用例

    | 格式 | 使用说明 | 实例 |
    | :--- | :--- | :--- |
    | run -tc 测试用例文件名(无后缀) | 只支持devicetest类型的python用例 | run -tc XXX |


  - run --retry

    重新运行上一次的任务或者指定session的失败用例，重新生成测试报告。

    如下所示，实例输入了一个session id，那么框架将在报告路径下找到这个包含这个session id的目录，从smmary_report.html中解析出失败用例，重新运行。

    | 格式 | 使用说明 | 实例 |
    | :--- | :--- | :--- |
    | run --retry [--session session路径] | 如不指定session则重新运行上次失败的用例。否则，执行session中的失败用例 | run --retry <br> run --retry --session 2022-10-12-12-12-12 |


## 2.约束选项

> 约束选项，可以用于修饰执行选项也可以修饰约束选项。单独的约束选项和run命令的组合是无法被框架理解和执行的。

  - -sn

    通过设置参数的值来指定运行的设备

    | 格式 | 使用说明 | 实例 |
    | :--- | :--- | :--- |
    | -sn 设备唯一标识号 | 参数后的值为：sn号或id：port的字符格式。多个设备之间以分号分隔。 | run acts -sn 10.117.22.3:123 <br> run acts -sn 12321412;123213123 |

 - -rp

    指定报告生成路径。长选项表示为"--reportpath"。默认会在项目的reports文件夹下用时间戳或任务id建立子目录。

    如下所示，示例将报告生成路径进行了更改。本次执行任务的报告将生成在指定目录下。

    | 格式 | 使用说明 | 实例 |
    | :--- | :--- | :--- |
    | -rp 指定路径 | 使用指定的路径将体态默认的报告生成路径 | run acts -rp /suites/hits/resport/XXXX  |

 - -respath

    指定测试所需要的资源路径。长选项表示为"--resourcepath"。如果设置了此参数，框架在加载资源时，会在指定目录下查找。

    如下所示，示例设置了对应的资源路径。那么任务后续将在此目录下读取对应的资源进行操作。

    | 格式                    | 使用说明                                                     | 实例                                        |
    | :---------------------- | :----------------------------------------------------------- | :------------------------------------------ |
    | -respath 指定的资源路径 | 资源目录默认为项目下的resoucre。如果用户设置了此参数，则将资源目录设为指定文件夹 | run acts -respath /suites/hits/res/resuorce |

 - -ta

    指定测试套运行参数，约束测试套在运行时的行为。长选项表示为"--targets"。-ta后的参数最终会被框架获取、解析、拼接成命令。

    如下所示，-ta后的值将被框架读到，并指定模块后续行为。

    以下可用参数只对OHJS驱动有效

    | 可用参数 | 使用说明 | 实例 |
    | :--- | :--- | :--- |
    | class | 可以指定运行测试套中的指定用例，多个用例间以逗号分隔。 | run -l SoundTriggerTest -ta class:android.harware.SoundTriggerTest#testKey，解释：只运行SoundTriggerTest测试套下的testKey用例，SoundTriggerTest中其他用例均不执行 |
    | notClass | 指定不允许测试套中的哪些用例 | run -l SoundTriggerTest -ta notClass:android.harware.SoundTriggerTest#testKey，解释：除了SoundTriggerTest测试套下的testKey用例，SoundTriggerTest中其他用例均执行 |
    | stress | 指定测试套的运行次数 | run -l SoundTriggerTest -ta stress:100，解释：将测试套SoundTriggerTest运行100次 |
    | level | 用例级别，可选参数："0","1","2","3" | run -l SoundTriggerTest -ta level:1，解释：指定测试套SoundTriggerTest的用例级别为1 |
    | size | 用例粒度，可选参数："small","medium","large" | run -l SoundTriggerTest -ta size:small，解释：指定测试套SoundTriggerTest的用例粒度为small |
    | testType | 用例测试类型，可选参数："function","performance","reliability","security" | run -l SoundTriggerTest -ta testType:function，解释：指定测试套SoundTriggerTest的测试用例类型为function |

 - -pt

    指定-ta选项后的值的解析方式。长选项表示为"--passthrough"。需要配合-ta使用。-ta选项后的值，框架默认他是以组合方式存在的，多个组合之间以分号进行分隔。组合中如果存在多个元素，则元素之间以逗号进行分隔。

    | 格式 | 使用说明 | 实例 |
    | :--- | :--- | :--- |
    | -pt true/false | 如果指定为true，则-ta参数的值会被框架整体作为一个字符串来解析。如果为false，则会按照默认的方式解析 | run hits -ta size:large -pt false |

 - -env

    指定配置文件内容。长选项表示为"-- environment"。用户设置了配置文件内容后，框架将不再读取config/user_config.xml，而是解析指定的xml字符串内容。

    | 格式 | 使用说明 | 实例 |
    | :--- | :--- | :--- |
    | -env xml字符串 | Xml字符串必须符合user_config.xml规范。并且各个层级之间不允许存在换行符 | run -l XXXTest -env xxx |

 - -c

    指定当前任务的user_config.xml所在路径。长选项表示为"--config"。参数为一段有效路径。同-env命令有些相似，不过-env命令是将整个xml内容输入。

    | 格式 | 使用说明 | 实例 |
    | :--- | :--- | :--- |
    | -c 包含user_config.xml的路径 | 框架将优先从指定路径中去读取user_config.xml | run -l XXXTest -c xxx |

 - -t

    指定当前任务的测试类型。长选项表示为"--testtype"。其值主要使用在可视化报告中，默认为Test。可选类型有UT，MST，ST，PERF，SEC，RELI，DST，All。

    | 格式 | 使用说明 | 实例 |
    | :--- | :--- | :--- |
    | -t 类型名 | 如不填写，summary_report.html中默认为Test | run -l XXXTest -t ALL |

 - -td

    指定当前任务使用的驱动id。长选项表示为"--testdriver"。可填写的内容详见[测试支撑套件配置中的driver类型]()。
    
    如下所示，ANSModuleTest模块使用CppTest作为驱动id。框架会使用CppTest的对应驱动执行任务。

    | 格式 | 使用说明 | 实例 |
    | :--- | :--- | :--- |
    | -td 驱动id | 驱动id必须是框架提供的类型字符串 | run -l ANSModuleTest -td CppTest |

 - -tcpath

    指定用例测试用例路径。长选项表示为"--testcasespath"。框架默认使用项目下的testcase文件夹作为用例路径，如果指定了用例路径，则在指定路径下查找测试用例。

    | 格式 | 使用说明 | 实例 |
    | :--- | :--- | :--- |
    | -tcpath 用例路径 |  | run -l XXXTest -tcpath D:/xxxx/xxxx |

 - --session

    指定运行session id下的内容。约束选项，需配合--retry使用。

    如下所示，示例中指定了session id。框架在执行retry操作时，会在报告路径下寻找对应的文件进行解析，获取到失败的测试用例列表，然后重新执行。

    | 格式 | 使用说明 | 实例 |
    | :--- | :--- | :--- |
    | --session sessionID | 重新执行指定sessionid中的失败用例 | run --retry --session 2022-12-11-12-11-22 |

 - --dryrun

    列举上次失败的测试用例选项。约束参数，需配合--retry使用。结果集打印分成几大部分。

    > Session id：框架记录的上次任务的Session编号

    > Command：上次任务使用的命令

    > ReportPath：上次任务报告路径

    > CasesInfo：上次任务的用例选项，包括模块（Module）、测试套（TestSuit）、测试用例（TestCase）

    | 格式 | 使用说明 | 实例 |
    | :--- | :--- | :--- |
    | run --retry --dryrun | 固定用法。用于获取上次的失败用例的详细信息。结果分列显示在控制台上 | run --retry --dryrun |

 - --reboot-per-module

    指定执行本次任务的模块前是否重启设备。

    | 格式 | 使用说明 | 实例 |
    | :--- | :--- | :--- |
    | --reboot-per-module | 直接在命令后输入执行项名即可 | run -l ANSTest --reboot-per-module |

 - --check-device

    验证设备。

    如果设备不一致，则会出现错误"does not meet the requirement"。

    | 格式 | 使用说明 | 实例 |
    | :--- | :--- | :--- |
    | --check-device | 验证ssts.json里properties的spt与实际运行的设备是否一致 | run ssts -l XXXTest --check-device  |
    
 - --repeat

    重复执行次数

    | 格式     | 使用说明                                 | 实例                                                |
    | :------- | :--------------------------------------- | :-------------------------------------------------- |
    | --repeat | 在--repeat后空格，输入需要重复执行的次数 | run ssts -l XXX --repeat 3,表示重发运行XXX测试套3次 |

 - -tl

    长选项表示为"--testlevel",此参数为保留选项，目前框架没有使用到

 - -cov

    长选项表示为"--coverage",此参数为保留选项，目前框架没有使用到

 - -bv

    长选项表示为"--build_variant",此参数为保留选项，目前框架没有使用到
