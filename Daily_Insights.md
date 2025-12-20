L1 Describes the current machine status (200) and the time range of the statuses --> all data besides inside 200 Code is not relevant
L2 Describes the errors that lead to a machine stop --> relevant are the camera related stops
L3 is the actual measured values from the camera systems


# Insights Day 1

1. Data - > All about "spark-machine-otto-vision-dynamic" machine

2. Machine Status code -> 200 is for Production / Runnning in Dataset 1 5DayCameraMetadata

3. LTL, UTL -> Lower Tolarance , Upper Tolerance Values
 
4. 5 days camera data -> X 
    &&&&& 
    metadata L2 -> Y 
    where we have to decide wheather to stop/ notify for anamoly

5. 5 Day camera data 
    a. Multiple devices simultaneously working giving outputs -> Stored without any format or sequence in dataset

    b. Variable Attribute field -> 
     [lowerLimit: -0.2, upperLimit: 0.2, nominalValue: 2.7, engineeringUnits: mm, cavity: 1]  

    c. {device_name == machine_id} in other 2 datasets
        de512stmp223 == s-223
        total -> ['de512stmp223', 'de512stmp226', 'de512stmp268', 'de512stmp269', 'de512stmp276', 'de512stmp278]
        others ->['S-276', 'S-226', 'S-269', 'S-268', 'S-223', 'S-278']

6. 5 Days of Metadata -> Given Starting and ending of the machine (We have to select only the Production i.e. code = 200 once) 

7. Sequence -> 
        1. 5Day Camera Metadata -> Consider D1
            2. 5 Day Camera Data (Actual Data) -> Consider D2 
                3. Metadata L2 (Actual OP we have to predict) -> Consider D3



# Insights Day 2 
### Date: 16-12-2025 09:12 

1. **Parquet** is very fast to load 
    - After converting the data in parquet total size **612 mb** (before 1.6 gb)
2. Camera data
    - Change the machine name to match other datasets
    - Splitted **variable_attribute** feature into 4 features
    - Removed single values columns like 
        -"lowerLimit", "upperLimit","nominalValue", "cavity"
    
    - Tried to split the **value** field took so much **time**

    - **Stored parquet of current status of data**
3. Visulisation insights
    - Added new field called **avg_value** containig avg of all 100 values in the value fiels
    - Plotted graphs for some related variables for same machine
        - Insights
            - There are some **outliers** which not leting graph plot well
            - Able to see the actual variations in the values by plotting "**spur1Iso**" variable machine- S-268


# Insights Day 3 
### Date: 18-12-2025 09:12 

1. d1
    - Each **part_number** is matching with each **tool_number** uniquely
        part_number    tool_number
        2-1703930-1    [S1956413]
        2-1703930-2    [S1829661]
        5-2208763-3    [S1829103]
        5-963715-1     [S0275910]
        5-965906-1     [S0025195]
        7-1452668-3    [S1829585]
2. Plotted graphs **(avg_value to time)** with and without *upper* and *lower* limits 
    per **machine** per **timestamp** (start to end) per **variable** in visulisation 1
3. Some **outlier** values when doing mean **shoot** **out** of graph we have to handle them
4. **No graph plotted is outside the given upper and lower limits**

5. ##### Now we have to plot the points on the graph where the anamoly is detected and pointed out in final file