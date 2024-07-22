#!/bin/bash
#
#

rm -rf docs/testfiles/
mkdir -p docs/testfiles/
echo "{}" > docs/testfiles/setup.json

echo "# Screenshots (testfile)" > docs/testfiles/README.md
echo "" >> docs/testfiles/README.md
echo "screenshots of the testfiles in tests/data/ loaded in viaconstructor with the default configuration" >> docs/testfiles/README.md
echo "" >> docs/testfiles/README.md

for IMG in `ls tests/data/* | grep -v "\.check$\|\.cfg\|\.xnc\|\.scad"`
do

    #echo ../../$IMG
    #continue

    echo -n > /tmp/vlog
    echo "viaconstructor $IMG"
    viaconstructor -s docs/testfiles/setup.json -D $IMG 2> /tmp/vlog &
    for n in `seq 20`
    do
        cat /tmp/vlog
        if grep -s -q "update_drawing: done" /tmp/vlog
        then
            sleep .5
            import -silent -quiet -window "viaConstructor" docs/testfiles/`basename $IMG`.png
            
            echo "## `basename $IMG`" >> docs/testfiles/README.md
            echo "drawing: [`basename $IMG`](../../$IMG)" >> docs/testfiles/README.md
            echo "" >> docs/testfiles/README.md
            echo "<img src=\"`basename $IMG`.png\" width=\"320\">" >> docs/testfiles/README.md
            echo "" >> docs/testfiles/README.md
            
            break
        fi
        sleep .5
    done
    killall -9 viaconstructor
    sleep .5

    
    if echo "$IMG" | grep -s -q "\.svg"
    then
        echo -n > /tmp/vlog
        echo "viaconstructor --dxfread-no-svg $IMG"
        viaconstructor -s docs/testfiles/setup.json -D --dxfread-no-svg $IMG 2> /tmp/vlog &

        for n in `seq 20`
        do
            if grep -s -q "update_drawing: done" /tmp/vlog
            then
                sleep .5
                import -silent -quiet -window "viaConstructor" docs/testfiles/`basename $IMG`--dxfread-no-svg.png

                echo "## `basename $IMG`" >> docs/testfiles/README.md
                echo "drawing: [`basename $IMG`](../../$IMG)" >> docs/testfiles/README.md
                echo "" >> docs/testfiles/README.md
                echo "with option: --dxfread-no-svg" >> docs/testfiles/README.md
                echo "" >> docs/testfiles/README.md
                echo "<img src=\"`basename $IMG`--dxfread-no-svg.png\" width=\"320\">" >> docs/testfiles/README.md
                echo "" >> docs/testfiles/README.md

                break
            fi
            sleep .5
        done
        killall -9 viaconstructor
        sleep .5
    fi

    
    if echo "$IMG" | grep -s -q "\.bmp"
    then
        echo -n > /tmp/vlog
        echo "viaconstructor --dxfread-no-bmp $IMG"
        viaconstructor -s docs/testfiles/setup.json -D --dxfread-no-bmp --imgread-scale 10 $IMG 2> /tmp/vlog &

        for n in `seq 20`
        do
            if grep -s -q "update_drawing: done" /tmp/vlog
            then
                sleep .5
                import -silent -quiet -window "viaConstructor" docs/testfiles/`basename $IMG`--dxfread-no-bmp--imgread-scale10.png

                echo "## `basename $IMG`" >> docs/testfiles/README.md
                echo "drawing: [`basename $IMG`](../../$IMG)" >> docs/testfiles/README.md
                echo "" >> docs/testfiles/README.md
                echo "with option: --dxfread-no-bmp --imgread-scale 10" >> docs/testfiles/README.md
                echo "" >> docs/testfiles/README.md
                echo "<img src=\"`basename $IMG`--dxfread-no-bmp--imgread-scale10.png\" width=\"320\">" >> docs/testfiles/README.md
                echo "" >> docs/testfiles/README.md

                break
            fi
            sleep .5
        done
        killall -9 viaconstructor
        sleep .5
    fi
done



