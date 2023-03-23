@echo off 

set filename="%1"
if "%filename:"=.%"==".." (
    Python310\python.exe -m viaconstructor tests\data\simple.dxf
) else (
    Python310\python.exe -m viaconstructor %filename
)
