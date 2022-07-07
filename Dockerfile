
FROM debian:11

RUN apt-get update
RUN apt-get -y install python3 python3-pip libglib2.0-0 libgl1 libqt5gui5 libglu1-mesa

COPY ./ /usr/src/viaconstructor

RUN pip3 install -r /usr/src/viaconstructor/requirements.txt

RUN echo "cd /usr/src/viaconstructor ; python3 -m viaconstructor tests/data/simple.dxf" > /usr/src/init.sh && chmod 755 /usr/src/init.sh

CMD ["/bin/bash", "/usr/src/init.sh"]

