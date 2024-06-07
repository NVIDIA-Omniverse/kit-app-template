# Data Collection & Use


## Overview


NVIDIA Omniverse Kit Application Template collects anonymous usage data to help improve software performance and aid in diagnostic purposes. Rest assured, no personal information such as user email, name or any other PII field is collected.


## Purpose


Omniverse Kit Application Template starts collecting data when you begin interaction with our provided software.
It includes:-
- Installation and configuration details such as version of operating system, applications installed : Allows us to recognize usage trends & patterns
- Hardware Details such as CPU, GPU, monitor information : Allows us to optimize settings in order to provide best performance
- Product session and feature usage : Allows us to understand user journey and product interaction to further enhance workflows
Error and crash logs : Allows us to improve performance & stability for troubleshooting and diagnostic purposes of our software




## Turn off Data Collection


To turn off data collection, you must need to change a setting:


1. After creating an application with the `template new` tooling, go to the `source/apps` directory
2. Locate the `.kit` file for the application you want to disable telemetry for.
3. Find the following section in the `.kit` file:


   ```toml
       [settings.telemetry]
       # Anonymous Kit application usage telemetry
       enableAnonymousData = true
   ```
4. Change `enableAnonymousData` to `false`:


   ```toml
       [settings.telemetry]
       # Anonymous Kit application usage telemetry
       enableAnonymousData = false
   ```


Disabling telemetry stops data collection from your application.
