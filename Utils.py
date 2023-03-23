import h5py
import argparse
import fastjet as fj
import numpy as np
import sys
from PlotUtils import *
import ROOT
from array import array
import copy

ROOT.gROOT.SetBatch(True)
ROOT.gStyle.SetOptStat(False)
h_dummy = None

sys_weights_map = {
        'nom_weight' : 0,
        'pdf_up' : 1,
        'pdf_down': 2,
        'prefire_up': 3,
        'prefire_down' : 4,
        'pileup_up' : 5 ,
        'pileup_down' : 6,
        'btag_up' : 7,
        'btag_down' : 8,
        'PS_ISR_up' : 9,
        'PS_ISR_down' : 10,
        'PS_FSR_up' : 11,
        'PS_FSR_down' : 12,
        'F_up' : 13,
        'F_down' : 14,
        'R_up' : 15,
        'R_down' : 16,
        'RF_up' : 17,
        'RF_down' : 18,
        'top_ptrw_up' : 19,
        'top_ptrw_down' : 20,
        'mu_trigger_up': 21,
        'mu_trigger_down': 22,
        'mu_id_up': 23,
        'mu_id_down': 24,
        'bkg_norm_up': -999,
        'bkg_norm_down': -999,
        }

sig_sys = {
        'pdf_up' : 1,
        'pdf_down': 2,
        'prefire_up': 3,
        'prefire_down' : 4,
        'btag_up' : 7,
        'btag_down' : 8,
        'F_up' : 13,
        'F_down' : 14,
        'R_up' : 15,
        'R_down' : 16,
        'RF_up' : 17,
        'RF_down' : 18,
        'top_ptrw_up' : 19,
        'top_ptrw_down' : 20,
        'mu_trigger_up': 21,
        'mu_trigger_down': 22,
        'mu_id_up': 23,
        'mu_id_down': 24,
        }

        
def input_options():
#input options for all the of the different scripts. Not all options are used for everything

    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--fin", default='', help="Input file")
    parser.add_argument("-o", "--outdir", default='test/', help="Output directory")
    parser.add_argument("--charge_only", default=False, action='store_true', help="Only charged particles in Lund Plane")
    parser.add_argument("--no_sys", default=False, action='store_true', help="No systematics")
    return parser


def cleanup_hist(h):
    if(type(h) == ROOT.TH3F):
        for i in range(h.GetNbinsX()+1):
            for j in range(h.GetNbinsY()+1):
                for k in range(h.GetNbinsZ()+1):
                    c = h.GetBinContent(i,j,k)
                    if( c < 0): 
                        h.SetBinContent(i,j,k, 0.)
                        h.SetBinError(i,j,k, 0.)
    elif(type(h) == ROOT.TH2F):
        for i in range(h.GetNbinsX()+1):
            for j in range(h.GetNbinsY()+1):
                c = h.GetBinContent(i,j)
                if( c < 0): 
                    h.SetBinContent(i,j, 0.)
                    h.SetBinError(i,j, 0.)



def copy_proj(bin_i, h_ratio_proj, h_ratio):
    for j in range(h_ratio.GetNbinsY()):
        for k in range(h_ratio.GetNbinsZ()):
            h_ratio.SetBinContent(bin_i,j,k, h_ratio_proj.GetBinContent(j,k))
            h_ratio.SetBinError(bin_i,j,k, h_ratio_proj.GetBinError(j,k))
    return

def get_unc_hist(h):
    h_unc = h.Clone(h.GetName() + "_unc")
    for i in range(1, h.GetNbinsX() + 1):
        for j in range(1, h.GetNbinsY() + 1):
            err = h.GetBinError(i,j)
            cont = h.GetBinContent(i,j)

            if(cont > 0):
                h_unc.SetBinContent(i,j, err/cont)
                h_unc.SetBinError(i,j, 0.)
            else:
                h_unc.SetBinContent(i,j, 0.)
    return h_unc


def cleanup_ratio(h, h_min = 0., h_max = 2.):
    for i in range(1, h.GetNbinsX() + 1):
        for j in range(1, h.GetNbinsY() + 1):
            cont = h.GetBinContent(i,j)
            cont = max(h_min, min(cont, h_max))
            h.SetBinContent(i,j,cont)
    #h.GetZAxis().SetRangeUser(h_min, h_max);

def convert_4vec(vec):
    rvec = ROOT.Math.PtEtaPhiMVector(vec[0], vec[1], vec[2], vec[3])
    return [rvec.Px(), rvec.Py(), rvec.Pz(), rvec.E()]


def ang_dist(phi1, phi2):
    phi1 = phi1 % (2. * np.pi)
    phi2 = phi2 % (2. * np.pi)
    dphi = phi1 - phi2
    dphi[dphi < -np.pi] += 2.*np.pi
    dphi[dphi > np.pi] -= 2.*np.pi
    return dphi

def get_subjet_dist(q_eta_phis, subjets_eta_phis):
    q_eta_phis = np.expand_dims(q_eta_phis, 0)
    subjets_eta_phis = np.expand_dims(subjets_eta_phis, 1)
    print(q_eta_phis.shape)
    print(subjets_eta_phis.shape)
    return np.sqrt(np.square(subjets_eta_phis[:,:,0] - q_eta_phis[:,:,0]) + 
            np.square(ang_dist(subjets_eta_phis[:,:,1], q_eta_phis[:,:,1] )))


def get_dists(q_eta_phis, subjets_eta_phis):
    q_eta_phis = np.expand_dims(q_eta_phis, 2)
    subjets_eta_phis = np.expand_dims(subjets_eta_phis, 1)
    #print(q_eta_phis.shape)
    #print(subjets_eta_phis.shape)
    return np.sqrt(np.square(subjets_eta_phis[:,:,:,0] - q_eta_phis[:,:,:,0]) + 
            np.square(ang_dist(subjets_eta_phis[:,:,:,1], q_eta_phis[:,:,:,1] )))


class Dataset():
    def __init__(self, f, is_data = False, label = "", color = "", jms_corr = 1.0):

        self.f = f
        self.is_data = is_data

        self.label = label
        self.color = color

        self.n_evts = f['event_info'].shape[-1]
        self.mask = f['jet_kinematics'][:,0] > 0.
        self.norm_factor = 1.0

        self.jms_corr = jms_corr
        self.sys_key = ""
        self.sys_power = 1.0

        self.norm_unc = 0.1


    def n(self):
        return np.sum(self.mask)

    def apply_cut(self, cut):
        self.mask = self.mask & cut
    
    def get_masked(self, key):
        return self.f[key][()][self.mask]

    def apply_sys(self, sys_key):
        if(sys_key not in sys_weights_map.keys()): 
            print("Invalid sys %s!")
            exit(1)
        self.sys_key = sys_key

    def get_weights(self):
        if(self.is_data): return np.ones(self.n())
        weights = self.get_masked('norm_weights') * self.norm_factor
        if(len(self.sys_key) > 0):
            sys_idx = sys_weights_map[self.sys_key]
            reweighting = np.power(self.get_masked('sys_weights')[:,sys_idx], self.sys_power)
            #reweighting = self.get_masked('sys_weights')[:,sys_idx]
            np.clip(reweighting, 0., 10.0)
            reweighting /= np.mean(reweighting)
            weights *=  reweighting
        return weights

    def compute_obs(self):
        eps = 1e-8
        feats = self.get_masked('jet1_extraInfo')
        kins = self.get_masked('jet_kinematics')
        self.tau21 = (feats[:,1] / (feats[:,0] + eps))
        self.tau32 = (feats[:,2] / (feats[:,1] + eps))
        self.tau43 = (feats[:,3] / (feats[:,2] + eps))
        if(feats.shape[1] > 7): self.DeepAK8_W_MD = feats[:,8]
        if(feats.shape[1] > 8): self.DeepAK8_W = feats[:,9]
        self.mSoftDrop = kins[:,3] * self.jms_corr
        self.pt = kins[:,0]
        self.nPF= feats[:,6]




    def fill_LP(self, h, jetR = 0.8, num_excjets = 2, prefix = "2prong", sys_variations = None, charge_only = False):

        pf_cands = self.get_masked("jet1_PFCands").astype(np.float64)
        splittings = subjets =  split = subjet = None
        if(prefix + "_splittings" in self.f.keys()):
            splittings = self.get_masked(prefix + "_splittings")
            subjets = self.get_masked(prefix + "_subjets")

        jet_kinematics = self.get_masked("jet_kinematics")
        nom_weights = self.get_weights()

        hists = [h]
        weights = [nom_weights]

        if(sys_variations is not None):

            all_sys_weights = self.get_masked('sys_weights')


            for sys in sys_variations.keys():
                #don't vary ttbar norm at the same time
                if(sys == 'bkg_norm_up'): weights_sys = nom_weights * (1. + self.norm_unc)
                elif(sys == 'bkg_norm_down'): weights_sys = nom_weights  * (1. - self.norm_unc)
                else:
                    sys_idx = sys_weights_map[sys]
                    weights_sys = nom_weights * all_sys_weights[:, sys_idx]

                weights.append(weights_sys)
                hists.append(sys_variations[sys])


            #for idx,h in enumerate(hists):
            #    h.Print()
            #    print(weights[idx][:10])


        weights = np.array(weights, dtype = np.float32)
        subjets = []
        for i,pf_cand in enumerate(pf_cands):
            if(splittings is not None):
                split = splittings[i]
                subjet = subjets[i]

            subjet, _ = fill_lund_plane(hists, pf_cands = pf_cand, jetR = jetR, subjets = subjet, splittings = split, 
                    num_excjets = num_excjets, weight = weights[:,i], charge_only = charge_only)
            subjets.append(subjet)

        return subjets
            





    def reweight_LP(self, rw, h_ratio, num_excjets = 2, uncs = False, max_evts =-1, prefix = "", 
            rand_noise = None,  pt_rand_noise = None, sys_str = ""):
    #always uncs for now

        LP_weights = []
        LP_uncs = []
        LP_smeared_weights = []
        pt_smeared_weights = []
        pf_cands = self.get_masked("jet1_PFCands").astype(np.float64)
        jet_kinematics = self.get_masked("jet_kinematics")



        splittings = subjets = split = subjet = None
        if(prefix + "_splittings" in self.f.keys()):
            print("Found " + prefix + "_splittings" )
            splittings = self.get_masked(prefix + "_splittings")
            subjets = self.get_masked(prefix + "_subjets")


        if(max_evts > 0 and pf_cands.shape[0] > max_evts):
            pf_cands = pf_cands[:max_evts]
            jet_kinematics = jet_kinematics[:max_evts]

        for i,pf_cand in enumerate(pf_cands):

            if(splittings is not None):
                split = splittings[i]
                subjet = subjets[i]

            rw, unc, smeared_rw, pt_smeared_rw  = rw.reweight_lund_plane(h_ratio, pf_cand, subjets = subjet, splittings = split,                                        
                    num_excjets = num_excjets, uncs = uncs, rand_noise = rand_noise, pt_rand_noise = pt_rand_noise, sys_str = sys_str)

            rw = max(rw, 1e-8)
            LP_weights.append(rw)
            if(rand_noise is not None):
                LP_smeared_weights.append(smeared_rw)
            if(pt_rand_noise is not None):
                pt_smeared_weights.append(pt_smeared_rw)
            if(rw >= 1e-6 and uncs):
                LP_uncs.append(unc)
            else:
                LP_uncs.append(0.)


        LP_weights = np.clip(np.array(LP_weights), 0., 10.)
        mean = np.mean(LP_weights)
        LP_weights /= mean

        LP_uncs /= mean
        if(rand_noise is None):
            return LP_weights, LP_uncs
        else:
            LP_smeared_weights = np.clip(np.array(LP_smeared_weights), 0., 10.)
            smear_means = np.mean(LP_smeared_weights, axis = 0)
            LP_smeared_weights /= smear_means

            pt_smeared_weights = np.clip(np.array(pt_smeared_weights), 0., 10.)
            pt_smear_means = np.mean(pt_smeared_weights, axis = 0)
            pt_smeared_weights /= pt_smear_means

            return LP_weights, LP_uncs, LP_smeared_weights, pt_smeared_weights
        
class LundReweighter():

    def __init__(self, jetR = -1, maxJets = -1, dR = 0.8, pt_extrap_dir = None, pt_extrap_val = 450., pf_pt_min = 1.0, charge_only = False) :

        self.jetR = jetR
        self.maxJets = maxJets
        self.charge_only = charge_only
        self.dR = 0.8
        self.pt_extrap_dir = pt_extrap_dir
        self.pt_extrap_val = pt_extrap_val
        self.pf_pt_min = pf_pt_min
        self.charge_only = False


    def get_splittings(self, pf_cands, num_excjets = -1):
        pjs = []
        pfs_cut = []
        for i,c in enumerate(pf_cands):
            if(c[3] > 0.0001):
                pj = fj.PseudoJet(c[0], c[1], c[2], c[3])

                if(pj.pt() > 1.0):
                    pfs_cut.append(c)

                pjs.append(pj)

        if(self.jetR < 0): R = 1000.0
        else: R = self.jetR
        #jet_algo = fj.cambridge_algorithm
        jet_algo = fj.kt_algorithm
        jet_def = fj.JetDefinition(jet_algo, R)
        cs = fj.ClusterSequence(pjs, jet_def)
        if(num_excjets < 0):
            js = fj.sorted_by_pt(cs.inclusive_jets())
            if(self.maxJets > 0):
                nMax = min(len(js), self.maxJets)
                js = js[:nMax]
        else:
            js = list(fj.sorted_by_pt(cs.exclusive_jets_up_to(num_excjets)))

            #for kt jets, recluster to get CA splittings
            if (jet_algo is fj.kt_algorithm):
                CA_R = 1000.
                js_new = []
                clust_seqs = []
                for i, j in enumerate(js):
                    CA_jet_def = fj.JetDefinition(fj.cambridge_algorithm, CA_R)
                    constituents = j.validated_cs().constituents(j)

                    cs_CA = []
                    for c in constituents:
                        if(c.pt() > self.pf_pt_min):
                            if(self.charge_only):
                                pf = find_matching_pf(pfs_cut, c)
                                if(pf is None):
                                    print("NO match!")
                                    print(c)
                                    print(pfs)
                                    exit(1)
                                #4th entry is PUPPI weight, 5th entry is charge of PFCand
                                eps = 1e-4
                                if(pf is not None and abs(pf[5] ) > eps):
                                    cs_CA.append(c)
                            else:
                                cs_CA.append(c)

                    if(len(cs_CA) > 0):
                        CA_cs = fj.ClusterSequence(cs_CA, CA_jet_def)
                        CA_jet = fj.sorted_by_pt(CA_cs.inclusive_jets())
                        js_new.append(j)
                        clust_seqs.append(CA_cs) #prevent from going out of scope

                js = js_new

        subjets = []
        splittings = []
        #print("%i subjets " % len(js))
        for i, j in enumerate(js):
            #print("sj %i" % i)
            pseudojet = j
            jet_pt = j.pt()
            subjets.append([j.pt(), j.eta(), j.phi(), j.m()])
            while True:
                j1 = fj.PseudoJet()
                j2 = fj.PseudoJet()
                if pseudojet and pseudojet.has_parents(j1, j2):
                    # order the parents in pt
                    if (j2.pt() > j1.pt()):
                        j1, j2 = j2, j1
                    # check if we satisfy cuts
                    delta = j1.delta_R(j2)
                    kt = j2.pt() * delta
                    splittings.append([i, delta, kt])
                    pseudojet = j1
                else:
                    break
        return subjets, splittings


    def fill_lund_plane(self, h, pf_cands = None, subjets = None,  splittings = None, num_excjets = -1, weight = 1., subjet_idx = -1):

        if(type(h) != list):
            hists = [h]
            weights = [weight]
        else:
            hists = h
            weights = weight
            #if (len(weights) > 1):
            #    print(weights)
            #    exit(1)

        if(subjets is None or splittings is None):
            subjets, splittings = self.get_splittings(pf_cands, num_excjets = num_excjets)
            if(len(subjets) == 0): subjets = [[0,0,0,0]]

        no_idx = (len(subjets) == 1)
        subjets = np.array(subjets).reshape(-1)

        for jet_i, delta, kt in splittings:
            if(subjet_idx >= 0 and jet_i != subjet_idx): continue
            jet_int = int(np.round(jet_i))
            jet_pt = subjets[0] if no_idx else subjets[jet_int*4]
            if(delta > 0. and kt > 0.):
                for h_idx, h in enumerate(hists):
                    if(type(h) == ROOT.TH3F): h.Fill(jet_pt, np.log(self.dR/delta), np.log(kt), weights[h_idx])
                    else: h.Fill(np.log(self.dR/delta), np.log(kt), weights[h_idx])
        return subjets, splittings



    def reweight_pt_extrap(self, subjet_pt, h_jet, rw, unc, smeared_rw, pt_smeared_rw, pt_rand_noise = None, sys_str = ""):
        fdir = self.pt_extrap_dir
        eps = 1e-4
        #should only be in last pt bin ? 
        i = h_jet.GetNbinsX()

        for j in range(1, h_jet.GetNbinsY() + 1):
            for k in range(1, h_jet.GetNbinsZ() + 1):
                n_cands = h_jet.GetBinContent(i,j,k)
                if(n_cands > 0): 
                    f = fdir.Get("func_%s%i_%i" % (sys_str, j,k))
                    val = f.Eval(subjet_pt)
                    val = np.maximum(val, eps)

                    rw *= val ** n_cands
                    #keep noise smeared vals consistent
                    if(smeared_rw is not None): smeared_rw *= val ** n_cands

                    if(pt_rand_noise is not None):
                        for n in range(pt_rand_noise.shape[0]):
                        #up_down = [-1., 1.]
                        #for n in range(2):
                            pars = array('d')
                            for p in range(f.GetNpar()):
                                pnom = f.GetParameter(p)
                                perr = f.GetParError(p)
                                #pnew = pnom + perr * up_down[n]
                                pnew = pnom + perr * pt_rand_noise[n, j, k, p]
                                pars.append(pnew)

                            smeared_val = f.EvalPar(array('d', [subjet_pt]), pars)
                            smeared_val = np.maximum(smeared_val, eps)
                            pt_smeared_rw[n] *= smeared_val ** n_cands


        return rw, unc, smeared_rw, pt_smeared_rw


    def reweight(self, h_rw, h_jet, rw, unc, smeared_rw, pt_smeared_rw, rand_noise = None):
        eps = 1e-4
        if(type(h_rw) == ROOT.TH3F):
            for i in range(1, h_jet.GetNbinsX() + 1):
                for j in range(1, h_jet.GetNbinsY() + 1):
                    for k in range(1, h_jet.GetNbinsZ() + 1):
                        n_cands = h_jet.GetBinContent(i,j,k)
                        if(n_cands > 0): 
                            #print("Rw %.3f, cont %.3f, i %i j %i k %i n %i" % (rw, h_rw.GetBinContent(i,j,k), i,j,k, n_cands))
                            val = h_rw.GetBinContent(i,j,k)
                            err = h_rw.GetBinError(i,j,k)
                            if(val <= 1e-4 and err <= 1e-4):
                                val = 1.0
                                err = 1.0
                            if(unc is not None): 
                                #uncertainty propagation
                                unc = ( (n_cands * rw * val**(n_cands -1) * err)**2 + (val**n_cands * unc)**2) ** (0.5)
                            if(rand_noise is not None):
                                smeared_vals = val + rand_noise[:,i-1,j-1,k-1] * err
                                smeared_vals = np.maximum(smeared_vals, eps)
                                smeared_rw *= smeared_vals ** n_cands

                            rw *= val ** n_cands
                            #keep pt smearing vals consistent
                            if(pt_smeared_rw is not None): pt_smeared_rw *= val ** n_cands

        else:
            for i in range(1, h_jet.GetNbinsX() + 1):
                for j in range(1, h_jet.GetNbinsY() + 1):
                    n_cands = h_jet.GetBinContent(i,j)
                    if(n_cands > 0): 
                        val = h_rw.GetBinContent(i,j)
                        if(unc is not None): 
                            err = h_rw.GetBinError(i,j)
                            #uncertainty propagation
                            unc = ( (n_cands * rw * val**(n_cands -1) * err)**2 + (val**n_cands * unc)**2) ** (0.5)
                        rw *= val ** n_cands
        return rw, unc, smeared_rw, pt_smeared_rw



    def reweight_lund_plane(self, h_rw, pf_cands = None, splittings = None, subjets = None, num_excjets = -1, weight = 1., 
                            uncs = False, rand_noise = None, pt_rand_noise = None,  sys_str = ""):

        global h_dummy
        if(h_dummy is None): h_dummy = h_rw.Clone("dummy")
        h_dummy.Reset()

        if(subjets is None or splittings is None):
            subjets, splittings = self.get_splittings(pf_cands, num_excjets = num_excjets )


        rw = 1.0
        if(uncs): unc = 0.0
        else: unc = None

        pt_smeared_rw = smeared_rw = None

        if(rand_noise is not None): smeared_rw = np.array([1.0]*rand_noise.shape[0])
        if(pt_rand_noise is not None): pt_smeared_rw = np.array([1.0]*pt_rand_noise.shape[0])


        for i in range(len(subjets)):

            self.fill_lund_plane(h_dummy, pf_cands = pf_cands, splittings = [splittings[i]], subjets = [subjets[i]], num_excjets = num_excjets, weight = weight)

            if(pt_extrap_dir is None or subjets[i][0] < pt_extrap_val):
                rw, unc, smeared_rw, pt_smeared_rw = self.reweight(h_rw, h_dummy, rw, unc, smeared_rw, pt_smeared_rw, rand_noise = rand_noise)
            else:
                rw, unc, smeared_rw, pt_smeared_rw = self.reweight_pt_extrap(subjets[i][0], h_dummy, rw, unc, smeared_rw, pt_smeared_rw, pt_rand_noise = pt_rand_noise, sys_str = sys_str)

        #h_jet.Scale(1./h_jet.Integral())
        #h_jet.Multiply(h_rw)





        #h_jet.Print("range")
        
        return rw, unc, smeared_rw, pt_smeared_rw


    def make_LP_ratio(self, h_data, h_bkg, h_mc, pt_bins, outdir = "", save_plots = False):


        h_data.Print()
        h_bkg.Print()
        h_mc.Print()

        cleanup_hist(h_mc)
        cleanup_hist(h_bkg)

        h_bkg_clone = h_bkg.Clone(h_bkg.GetName() + "_clone")
        h_mc_clone = h_mc.Clone(h_mc.GetName() + "_clone")

        data_norm = h_data.Integral()
        est = h_bkg_clone.Integral() + h_mc_clone.Integral()


        h_bkg_clone.Scale(data_norm / est)
        h_mc_clone.Scale(data_norm / est)

        h_ratio = h_data.Clone(h_mc_clone.GetName() + "_ratio")
        h_ratio.SetTitle("(Data - Bkg ) / TTbar MC")

        h_data_sub = h_data.Clone("h_data_sub")
        h_data_sub.Add(h_bkg_clone, -1.)
        h_data_sub.Print()


        cleanup_hist(h_data_sub)


        for i in range(1, h_data.GetNbinsX() + 1):
            h_bkg_clone1 = h_bkg_clone.Clone("h_bkg_clone%i" %i)
            h_mc_clone1 = h_mc_clone.Clone("h_mc_clone%i"% i)
            h_data_clone1 = h_data_sub.Clone("h_data_clone%i" %i)

            h_mc_clone1.GetXaxis().SetRange(i,i)
            h_bkg_clone1.GetXaxis().SetRange(i,i)
            h_data_clone1.GetXaxis().SetRange(i,i)


            h_mc_proj = h_mc_clone1.Project3D("zy")
            h_bkg_proj = h_bkg_clone1.Project3D("zy")
            h_data_proj = h_data_clone1.Project3D("zy")


            h_bkg_proj.Scale(1./h_bkg_proj.Integral())

            data_norm = h_data_proj.Integral()
            h_data_proj.Scale(1./data_norm)
            h_mc_proj.Scale(1./h_mc_proj.Integral())

            h_ratio_proj = h_data_proj.Clone("h_ratio_proj%i" %i)
            h_ratio_proj.Divide(h_mc_proj)

            #if(i == 1): 
            #    h_mc_proj.Print("range")
            #    h_data_proj.Print("range")
            #    h_ratio_proj.Print("range")

            copy_proj(i, h_ratio_proj, h_ratio)



            if(save_plots): 

                h_bkg_proj.SetTitle("Bkg MC pT %.0f - %.0f" % (pt_bins[i-1], pt_bins[i]))
                h_mc_proj.SetTitle("TTbar MC pT %.0f - %.0f" % (pt_bins[i-1], pt_bins[i]))
                h_data_proj.SetTitle("Data - Bkg pT %.0f - %.0f (N = %.0f)" % (pt_bins[i-1], pt_bins[i], data_norm))
                h_ratio_proj.SetTitle("Ratio pT %.0f - %.0f (N = %.0f)" % (pt_bins[i-1], pt_bins[i], data_norm))


                c_mc = ROOT.TCanvas("c", "", 1000, 1000)
                h_mc_proj.Draw("colz")
                c_mc.SetRightMargin(0.2)
                c_mc.Print(outdir + "lundPlane_bin%i_MC.png" % i)


                c_bkg = ROOT.TCanvas("c", "", 1000, 800)
                h_bkg_proj.Draw("colz")
                c_bkg.SetRightMargin(0.2)
                c_bkg.Print(outdir + "lundPlane_bin%i_bkg.png" % i)

                c_data = ROOT.TCanvas("c", "", 1000, 800)
                h_data_proj.Draw("colz")
                c_data.SetRightMargin(0.2)
                c_data.Print(outdir + "lundPlane_bin%i_data.png" %i )



                c_ratio = ROOT.TCanvas("c", "", 1000, 800)
                cleanup_ratio(h_ratio_proj, h_min =0., h_max = 2.0)
                h_ratio_proj.Draw("colz")
                c_ratio.SetRightMargin(0.2)
                c_ratio.Print(outdir + "lundPlane_bin%i_ratio.png" % i)

                h_ratio_unc = get_unc_hist(h_ratio_proj)
                cleanup_ratio(h_ratio_unc, h_min = 0., h_max = 1.0)
                c_ratio_unc = ROOT.TCanvas("c_unc", "", 800, 800)
                h_ratio_unc.SetTitle("Ratio pT %.0f - %.0f (N = %.0f) Relative Unc." % (pt_bins[i-1], pt_bins[i], data_norm))
                h_ratio_unc.Draw("colz")
                c_ratio_unc.SetRightMargin(0.2)
                c_ratio_unc.Print(outdir + "lundPlane_bin%i_ratio_unc.png" % i)
                h_ratio_unc.Reset()

        return h_ratio





def matched(c,cj):
    eps = 1e-4
    return (abs(c[0] - cj.px()) < eps) and (abs(c[1] - cj.py()) < eps) and (abs(c[2] - cj.pz()) < eps)


def find_matching_pf(cj_list, cj):
    for c in cj_list:
        if(matched(c, cj)): 
            return c
    return None

