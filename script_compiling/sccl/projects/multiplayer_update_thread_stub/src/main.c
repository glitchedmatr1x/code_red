/*
   Code RED multiplayer_update_thread SCO loader stub.

   Purpose:
   - Compile as RDR_SCO with output name multiplayer_update_thread.
   - Prove whether the active game can resolve/load an SCO script at the
     missing multiplayer_update_thread path.

   Boundary:
   - This is NOT the real multiplayer_update_thread implementation.
   - It does not initialize freeroam/session/net state.
   - Use only as a loader/asset-presence probe before attempting a real port.
*/

#include "../include/types.h"
#include "../include/intrinsics.h"
#include "../include/natives.h"
#include "../include/RDR/natives32.h"

void main(void)
{
    ADD_PERSISTENT_SCRIPT(_GET_ID_OF_THIS_SCRIPT());

    while (true)
    {
        WAIT(0);
    }
}
