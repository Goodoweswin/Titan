// Run in Fiji/ImageJ: -macro fiji_reference.ijm 'fixture.tif|reference.csv'
// Explicit pixel ROIs match the documented 40x20 golden fixture.
args = split(getArgument(), "|");
if (args.length != 2) exit("Expected image path|CSV output path");
open(args[0]);
run("Clear Results");
run("Set Measurements...", "area mean integrated redirect=None decimal=9");
makeRectangle(2, 25, 4, 4); run("Measure");
targetRaw = getResult("RawIntDen", 0); targetArea = getResult("Area", 0);
makeRectangle(2, 35, 4, 3); run("Measure"); targetBG = getResult("Mean", 1);
makeRectangle(2, 10, 2, 2); run("Measure");
refRaw = getResult("RawIntDen", 2); refArea = getResult("Area", 2);
makeRectangle(2, 2, 2, 2); run("Measure"); refBG = getResult("Mean", 3);
targetNet = targetRaw-targetArea*targetBG; refNet = refRaw-refArea*refBG;
File.saveString("target_raw,target_area,target_bg,target_net,reference_raw,reference_net,ratio\n"+targetRaw+","+targetArea+","+targetBG+","+targetNet+","+refRaw+","+refNet+","+targetNet/refNet+"\n", args[1]);
setOption("Changes", false); close();
