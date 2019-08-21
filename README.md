# USR-R16
This is a custom component for Home Assistant to integrate [USR-R16 16x relay switches module](https://www.zhize.com.cn/wangluojidianqi/16luwangluojidianqi.html).

# Setup
```
# configuration.yaml

usr_r16:
  relay1:
    host: 10.0.0.153
    password: admin
    switches:
      1:
        name: relay1-1
      2:
        name: relay1-2
      3:
        name: relay1-3
      4:
        name: relay1-4
      5:
        name: relay1-5
      6:
        name: relay1-6
      7:
        name: relay1-7
      8:
        name: relay1-8
      9:
        name: relay1-9
      10:
        name: relay1-10
      11:
        name: relay1-11
      12:
        name: relay1-12
      13:
        name: relay1-13
      14:
        name: relay1-14
      15:
        name: relay1-15
      16:
        name: relay1-16
```

Configuration variables:
- **host** (*Required*): The IP of your USR-R16.
- **password** (*Optional*): The password of your USR-R16. Default: admin
- **port** (*Optional*): The port of your USR-R16. Default: 8899.
- **switches** (*Required*): The array that contains the relays.
  - **relayid** (*Optional*): The array that contains the USR-R16 relays, each must be a number between 1 and 16 which each corresponds to a labeled relay switch on the USR-R16.
    - **name** (*Optional*): The name used to display the switch in the frontend. Default: relayid.
   
