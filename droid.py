import traceback

# Android imports
available = False
try:
    import android
    from jnius import autoclass
    # from android import activity
    # from android import runnable
    Intent = autoclass('android.content.Intent')
    PythonActivity = autoclass('org.renpy.android.PythonActivity')
    Uri = autoclass('android.net.Uri')
    available = True
except:
    traceback.print_exc()

def action_dial(exten):
    # python to java magic
    intent = Intent(Intent.ACTION_DIAL)
    uri = Uri.parse('csip:'+exten)
    intent.setData(uri)
    PythonActivity.mActivity.startActivity(intent)

