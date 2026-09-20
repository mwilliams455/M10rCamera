#!/usr/bin/env python3
"""Pinned public-SDK comparison and original M10-R control-sweep audit, NOT ISP emulation.
Usage: sdkbridge1a.py SECTIONS REPO_ROOT SDK_SOURCES OUT_DIR
SDK_SOURCES is the root containing MILB_API/. External SDK code is read, never executed.
"""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,random,re,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM,CS_MODE_THUMB,CS_GRP_JUMP,CS_GRP_CALL
from capstone.arm import ARM_OP_IMM

SDK_REPO='ZMlogicL/companyTask'
SDK_COMMIT='f5fc84bd5c475f4c15017b7bff749f81c3618287'
SDK_HASHES={
'MILB_API/MILB_Header/include/Image/fr2y6a.h':'46901a26cc8e3416e9340a9a280865b8bbb0fa5e76a2361c662d82e09bcdf7c8',
'MILB_API/Project/ComponentTest/src/ctimr2yclassh.c':'68d6cbe78997aaa536eb963f22ef849b16edf4bb3651439d8cacc3a1ee5eab80',
'MILB_API/Project/ImageMacro/src/imr2y3.h':'f53867eeeefeca41e589690414d7a395246b1a164e919b527ce247bc7bfef599',
'MILB_API/Project/ImageMacro/src/imr2yctrl.h':'eb4d28ecfddba5165f7fb69e6b66a7e25e5d3d612ad722d5281fd62150fd73d1',
'MILB_API/Project/ImageMacro/src/imr2yctrl2.c':'5dd18f89963ba37e29ecdc527f2d4407eb86648d94ab428412d53dcc8fe2b03d',
'MILB_API/Project/ImageMacro/src/imr2yctrl2.h':'8d886917870687a5af1a512180d5dab52b504c17da861b456a2d022976397dc8'}
AUDIT_SHA='95d5d3a0663a73261facc888144afcae784c889b6dd9e7e04d02467ca1481313'

def sha(b): return hashlib.sha256(b).hexdigest()
def load(path):
    spec=importlib.util.spec_from_file_location('retained_bit15_audit',path)
    if spec is None or spec.loader is None:raise RuntimeError(str(path))
    m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m

def main():
    if not __debug__:raise RuntimeError('Assertions must stay enabled')
    ap=argparse.ArgumentParser(description=__doc__)
    for a in ['sections','repo','sdk','out']:ap.add_argument(a,type=Path)
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    texts={};sources=[]
    for p,h in SDK_HASHES.items():
        b=(a.sdk/p).read_bytes();assert sha(b)==h,p
        texts[Path(p).name]=b.decode('utf8')
        sources.append({'path':p,'bytes':len(b),'sha256':h,'git_blob_sha':hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest(),'url':f'https://github.com/{SDK_REPO}/blob/{SDK_COMMIT}/{p}'})
    anchors=[]
    def anchor(name,pattern,label):
        text=texts[name];m=re.search(pattern,text,re.S);assert m,(name,label)
        anchors.append({'file':name,'label':label,'first_line':text.count('\n',0,m.start())+1,'last_line':text.count('\n',0,m.end())+1})
        return m
    union=anchor('fr2y6a.h',r'union _IoR2yYblend\{.*?\}bit;\s*\};','named control-word declaration').group(0)
    assert re.findall(r'unsigned long\s*(\w*)\s*:(\d+);',union)==[('yyblnd','6'),('','2'),('ybblnd','6'),('','18')]
    anchor('fr2y6a.h',r'structure of yblend\s*\(2841_A120h\)','SDK register address (different from M10-R)')
    ycc=anchor('imr2yctrl2.h',r'/\*\* YC Convert control.*?\} R2yCtrlYcc;','SDK YC parameter structure and ratio descriptions').group(0)
    assert 'ycCoeff[3][3]' in ycc and '9bits signed' in ycc
    assert re.search(r'kuint16\s+yBlendRatio;',ycc) and re.search(r'kuint16\s+ybBlendRatio;',ycc)
    assert 'Luminance Y blend ratio (6bits 0 ~ 32)' in ycc
    assert 'Luminance Yb blend ratio (6bits 0 ~ 32)' in ycc
    assert len(re.findall(r'\b(?:kint16|kuint16)\s+',ycc))==3
    for field,label in [('YYBLND','yBlendRatio'),('YBBLND','ybBlendRatio')]:
        anchor('imr2yctrl2.c',rf'gImIoR2yRegPtr\[pipeNo\]->F_R2Y.YC.YBLEND.bit.{field} = r2y_ctrl_ycc->{label};',f'direct source assignment {field}')
        anchor('imr2yctrl2.c',rf'ycc_ctrl.YBLEND.bit.{field} = r2y_ctrl_ycc->{label};',f'RDMA source assignment {field}')
    anchor('imr2yctrl.h',r'kuint16\s+tone_yb_enable;.*?Performs TC to luminance Yb.*?\*/','SDK tone can separately act on Yb')
    anchor('imr2yctrl.h',r'kuint16\s+ytc_out;.*?YTc = Y\(coefficient "TCYC"\).*?YTc = Yb\(coefficient "CCYC"\).*?\*/','SDK Y and Yb coefficient-source distinction')
    anchor('imr2yctrl2.h',r'kuint16\s+gammaYbTblSimul;.*?\*/','SDK gamma Yb table control')
    anchor('imr2y3.h',r'r2y_ctrl_ycc.yBlendRatio = 0;\s*r2y_ctrl_ycc.ybBlendRatio = 0;','SDK sample configures zero/zero; not an observed pixel result')
    anchor('ctimr2yclassh.c',r'\.yBlendRatio = 0x3F,\s*\.ybBlendRatio = 0x3F,','SDK register test includes raw all-ones fields; not a valid image-mode proof')
    tool=a.repo/'tools/m10r_yblend_bit15_audit1a.py';assert sha(tool.read_bytes())==AUDIT_SHA
    audit=load(tool);images={}
    for name,h in audit.HASHES.items():
        b=(a.sections/name).read_bytes();assert sha(b)==h,name;images[name]=b
    img=images['092_IMG-System.bin'];sam=images['100_IMG-SAM7.bin']
    guards=audit.validate_identities(img,sam)
    ip=audit.Programmer(img);sp=audit.Programmer(sam,True)
    rng=random.Random(0xB2A65D26);counts={'img':0,'sam7':0};results_hash=hashlib.sha256()
    yc=[1224,2403,469,-691,-1357,2048,2048,-1715,-333]+[0x3fff]*6
    for first in range(64):
        for second in range(64):
            old=rng.randbytes(0x4000)
            pairs=[rng.getrandbits(16) for _ in range(4)]
            values=[first,second]+pairs
            expect=audit.expected_blend(old,values,False)
            got=ip.run(0xd4480,struct.pack('<6I',*values),old)
            assert got==expect
            sdk_word=(audit.u32(old,0x92c)&~0x3f3f)|first|(second<<8)
            assert audit.u32(got,0x92c)==sdk_word
            # Do not reinterpret the four unknown tail fields as SDK fields.
            packed=struct.pack('<15H2B4H',*[v&65535 for v in yc],first,second,*pairs)
            expect2=audit.expected_blend(audit.expected_ycc(old,yc,False),values,False)
            got2=sp.run(0x51da6,packed,old)
            assert got2==expect2
            assert audit.u32(got2,0x92c)==sdk_word
            counts['img']+=1;counts['sam7']+=1
            results_hash.update(got);results_hash.update(got2)
    assert not ip.bit15_changes and not sp.bit15_changes
    # Branch-encoding census, not a reachable-code proof. Scan every architectural alignment.
    direct=[];indirect_count=0;positive_control=[];decoded=0
    for label,mode,step in [('Thumb',CS_MODE_THUMB,2),('ARM',CS_MODE_ARM,4)]:
        md=Cs(CS_ARCH_ARM,mode);md.detail=True
        for off in range(4,len(sam)-3,step):
            for ins in md.disasm(sam[off:off+4],off,count=1):
                decoded+=1
                if not (ins.group(CS_GRP_JUMP) or ins.group(CS_GRP_CALL)):continue
                if ins.operands and ins.operands[-1].type==ARM_OP_IMM:
                    target=ins.operands[-1].imm
                    if 0x51da6<=target<0x51f1a:
                        direct.append({'mode':label,'pc':hex(off),'target':hex(target),'mnemonic':ins.mnemonic,'within_programmer':0x51da6<=off<0x51f1a})
                    if target==0x4d1b4:positive_control.append({'mode':label,'pc':hex(off),'mnemonic':ins.mnemonic})
                else:indirect_count+=1
    assert positive_control
    external=[x for x in direct if not x['within_programmer']]
    # Do not assert absence: retain any positive result if firmware input changes under new hashes.
    report={
      'status':'PASS_REGISTER_LAYOUT_COMPARISON_ONLY','gate_c_passed':False,
      'source_script_sha256':sha(Path(__file__).read_bytes()),
      'sdk':{'repository':SDK_REPO,'commit':SDK_COMMIT,'sources':sources,'anchors':anchors,
        'external_code_executed':False,'yyblnd':{'bits':[0,5],'description':'Luminance Y blend ratio','documented_range':[0,32]},
        'ybblnd':{'bits':[8,13],'description':'Luminance Yb blend ratio','documented_range':[0,32]},
        'Y_and_Yb_source_distinction':'Tone header distinguishes Y via TCYC and Yb via CCYC; Yb has separate tone-enable and gamma-table controls in this SDK.'},
      'firmware':{'section_sha256':audit.HASHES,'identity_guards':guards,'yc_matrix_field_bits':13,'sam7_structure_bytes':40,'yblend_control_address':'0x2002092c','normal_controls':[0,32],'fallback_controls':[0,0]},
      'exhaustive_six_bit_control_sweep':{'seed':'0xB2A65D26','distinct_control_pairs':4096,'original_executions':counts,'sdk_comment_range_pairs':1089,'outside_comment_range_pairs':3007,'comparison_window_bytes':16384,'concatenated_result_sha256':results_hash.hexdigest(),'paired_word_writes':ip.total_writes+sp.total_writes,'paired_word_bit15_changes':0,'stubs':['SAM7 0x4d1b4 and 0x4d118: existing clock-helper stubs'],'scope':'Exhaustive only over the two six-bit fields; sampled prior registers and four tail halfwords. No ISP pixels are computed.'},
      'sdk_equivalence_boundary':{'matching':'two control bit widths, positions, assignment order and grouping with YC conversion','mismatches':['SDK YC coefficients are nine-bit signed versus thirteen-bit M10-R register fields','SDK control word is 0x2841a120 versus M10-R 0x2002092c','SDK R2yCtrlYcc has 18 bytes of coefficients plus two uint16 ratios (22 bytes), not the M10-R 40-byte structure','SDK YC structure and writer lack the three YC and two Y BLEND paired words present in M10-R'],
        'assessment':'A specific Y/Yb field-role hypothesis is now supported by a related SDK. Same M10-R signal roles and pixel behavior are not proved.'},
      'sam7_branch_encoding_census':{'range':['0x4',hex(len(sam))],'decoded_candidates':decoded,'direct_targets_in_programmer':direct,'external_direct_targets':external,'indirect_candidates':indirect_count,'clock_helper_positive_controls':positive_control,'limitations':'Scans ARM/Thumb branch encodings at each alignment, including data candidates. Does not resolve indirect targets, runtime relocation, alternate mappings or reachability; no dead-code conclusion.'},
      'open':['M10-R SAM7 structure caller/producer','M10-R Y versus Yb signal mapping','mixing direction and denominator','meaning of the four paired fields','pixel-stage placement and source-signal scale','rounding, clipping and actual pixel equation'],
      'renderer_changed':False}
    (a.out/'sdkbridge_results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'executions':counts,'external_direct_targets':external,'indirect_candidates':indirect_count,'paired_writes':ip.total_writes+sp.total_writes,'result_sha256':results_hash.hexdigest()},indent=2))
if __name__=='__main__':main()
