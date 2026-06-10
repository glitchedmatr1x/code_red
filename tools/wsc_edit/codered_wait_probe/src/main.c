/*
   Code RED WSC edit source: codered_wait_probe
   Target archive path: root/content/release64/init/initpopulation.wsc

   This source compiles through SC-CL into an RDR #SC script, then Code RED
   converts the compiled XSC bytes into a WSC/RSC85 resource blob.
*/

#include "../include/types.h"
#include "../include/constants.h"
#include "../include/intrinsics.h"
#include "../include/natives.h"
#include "../include/RDR/natives32.h"
#include "../include/RDR/consts32.h"

void main(void)
{
    while (true)
    {
        WAIT(0);
    }
}
