import numpy as np
from solutions.util import j0
import h5py
from tqdm import tqdm
from scipy.interpolate import interp1d
from multiprocessing import Pool, cpu_count
from mpio import rsigmat_parallel
import pdb

def evaluate_J_H(inputname, r, sigma, t, outputname, axis=1, mp=True, skip=[]):

    '''
    Calculate mean intensity J and flux H at desired points in radius, 
    frequency, and time, given pre-calculated Fourier coefficients 
    J_n_sigma_omega.
    '''

    # Parallel processing setup
    cores = 8
    pool = Pool(processes=cores)

    # Load in some input variable arrays
    Jnsigmaomega = h5py.File(inputname, 'r')
    full_sigma = Jnsigmaomega['sigma'][:]
    omega = Jnsigmaomega['omega'][:110] # Temporary fix TO DO
    n = Jnsigmaomega['n'][:]
    d_omega = np.diff(omega)[0]
    R = r[-1]
    Jnsigmaomega.close()

    # Prepare output variable arrays
    aux_variables = [r, sigma, t]
    prim_variable = aux_variables.pop(axis)
    names = ['r', 'sigma', 't']
    name = names.pop(axis)

    # Create output file --- data will be filled in during loops
    output = h5py.File(outputname, 'w')
    output.create_dataset(names[0], data=aux_variables[0])
    output.create_dataset(names[1], data=aux_variables[1])
    output.create_dataset(name, data=prim_variable)
    output.close()

    if mp:
        pb = tqdm(total=len(t)*len(r)*len(n)*len(omega)*len(sigma))

        def save_queue_rsigmat(result):
            pb.update(len(prim_variable))
            Jsetname, Hsetname, J, H, fname = result
            output = h5py.File(fname, 'a')
            try:
                output.create_dataset(Jsetname, data=J)
                output.create_dataset(Hsetname, data=H)
            except:
                output[Jsetname][:] += J
                output[Hsetname][:] += H
            output.close()

        for l in range(len(n)):
            for m in range(len(omega)):
                kappa_n = n[l] * np.pi / R

                if m in skip:
                    continue

                # Load fourier coefficients for this n and omega
                Jnsigmaomega = h5py.File(inputname, 'r')
                Jdump = Jnsigmaomega['J_omega{}_n{}'.format(m, l)][:]
                J_interp = interp1d(full_sigma, Jdump)
                Jnsigmaomega.close()

                for i in range(len(aux_variables[0])):
                    for j in range(len(aux_variables[1])):
                        result = pool.apply_async(rsigmat_parallel, args=(inputname, i, j, l, m, n, J_interp, kappa_n, aux_variables, prim_variable, R, omega, d_omega, r, sigma, full_sigma, t, names, name, axis, outputname), callback=save_queue_rsigmat)    
        pool.close()
        pool.join()
        pb.close()
    else:
        output = h5py.File(outputname, 'a')
        pb = tqdm(total=len(t)*len(r)*len(n)*len(omega)*len(sigma))
        for l in range(len(n)):
            kappa_n = n[l] * np.pi / R
            for m in range(len(omega)):

                if m in skip:
                    continue

                # Load fourier coefficients for this n and omega
                Jnsigmaomega = h5py.File(inputname, 'r')
                Jdump = Jnsigmaomega['J_omega{}_n{}'.format(m, l)][:]

                if any(np.isnan(Jdump)):
                    Jdump = np.zeros(len(Jdump), dtype=np.complex)

                J_interp = interp1d(full_sigma, Jdump)
                Jnsigmaomega.close()

                for i in range(len(aux_variables[0])):
                    for j in range(len(aux_variables[1])):
                        J = np.zeros(len(prim_variable), dtype=np.complex)
                        H = np.zeros(len(prim_variable), dtype=np.complex)
                        for k in range(len(prim_variable)):

                            # Figure out which index goes with which variable
                            iters = [i, j, k]
                            order = np.argsort(np.array(names+[name]))
                            iters_ord = [iters[s] for s in order]
                            r_index, sigma_index, t_index = iters_ord

                            # Eq 34
                            J[k] += 2. * d_omega / (2.*np.pi) * J_interp(sigma[sigma_index]) * j0(kappa_n, r[r_index]) * np.exp(-1j*omega[m]*t[t_index])
                            j0_prime = np.cos(kappa_n*r[r_index])/r[r_index] - np.sin(kappa_n*r[r_index])/kappa_n/r[r_index]**2.
                            H[k] += - 2. * d_omega / (2.*np.pi) * J_interp(sigma[sigma_index]) * j0_prime * np.exp(-1j*omega[m]*t[t_index])
                            pb.update()

                        iterator = iters_ord.pop(axis)
                        Jsetname = 'J_{}{}_{}{}'.format(names[0], iters_ord[0], names[1], iters_ord[1])
                        Hsetname = 'H_{}{}_{}{}'.format(names[0], iters_ord[0], names[1], iters_ord[1])
                        try:
                            output.create_dataset(Jsetname, data=J)
                            output.create_dataset(Hsetname, data=H)
                        except:
                            output[Jsetname][:] += J
                            output[Hsetname][:] += H
        output.close()
        pb.close()


if __name__ == "__main__":
    r = [1e11, ]
    t = np.linspace(0., 2.*np.pi/0.01782804, 64)

    # TODO: Set max t to be equal to 2pi / minimum omega, and set n points to be equal to n omegas. Reproduce these outputs for 512, 256, and 128 omegas (also, the special 512 run with dt' = dt/4)

    sigma_eval = [1e7, 2e7] #np.linspace(-1e8, 1e8, 1001)
    inputname = './outputs/Jnso/n8_sigma10000_omega64_rk_debug.hdf5'
    outputname = './outputs/Jrst/r{}_sigma{}_t{}_64_rk_debug.hdf5'.format(len(r), len(sigma_eval), len(t))
    evaluate_J_H(inputname, r, sigma_eval, t, outputname, axis=2, mp=False,) #skip=[126, 127])
