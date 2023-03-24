MIT license 

https://github.com/jbuckmccready/CavalierContours

https://github.com/proto3/cavaliercontours-python


# for new platforms
you need to compile the CavalierContours sources from: https://github.com/jbuckmccready/CavalierContours

and moving the lib file to somthing like this:

 viaconstructor/ext/cavaliercontours/lib/libCavalierContours.x86_64-linux.so

edit the file:
 viaconstructor/ext/cavaliercontours/cavaliercontours.py

to load the right lib
