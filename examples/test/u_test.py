import math
import time
import torch
import numpy as np
torch.manual_seed(120)
from tqdm import tqdm
# from pytorch3d.loss import chamfer_distance
from NURBSDiff.nurbs_eval import SurfEval
from NURBSDiff.surf_eval import SurfEval as SurfEvalBS
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib import cm
from geomdl import exchange, utilities
from geomdl.visualization import VisMPL
from geomdl import compatibility
from torch.autograd.variable import Variable
import torch.nn.functional as F
# from scipy.spatial.distance import directed_hausdorff
# import offset_eval as off
import random

SMALL_SIZE = 12
MEDIUM_SIZE = 16
BIGGER_SIZE = 20

plt.rc('font', family='sans-serif') 
plt.rc('font', serif='Times') 
plt.rc('font', size=SMALL_SIZE)          # controls default text sizes
plt.rc('axes', titlesize=SMALL_SIZE)     # fontsize of the axes title
plt.rc('axes', labelsize=MEDIUM_SIZE)    # fontsize of the x and y labels
plt.rc('xtick', labelsize=SMALL_SIZE)    # fontsize of the tick labels
plt.rc('ytick', labelsize=SMALL_SIZE)    # fontsize of the tick labels
plt.rc('legend', fontsize=SMALL_SIZE)    # legend fontsize
plt.rc('figure', titlesize=BIGGER_SIZE)  # fontsize of the figure title


def read_weights(filename, sep=","):
    try:
        with open(filename, "r") as fp:
            content = fp.read()
            content_arr = [float(w) for w in (''.join(content.split())).split(sep)]
            return content_arr
    except IOError as e:
        print("An error occurred: {}".format(e.args[-1]))
        raise e
def generate_gradient(start_color, end_color, steps):
    # Convert the start and end colors to RGB tuples
    rgb_start = tuple(int(start_color[i:i+2], 16) for i in (1, 3, 5))
    rgb_end = tuple(int(end_color[i:i+2], 16) for i in (1, 3, 5))
    # Calculate the step size for each RGB component
    step_size = tuple((rgb_end[i] - rgb_start[i]) / (steps - 1) for i in range(3))
    # Generate the gradient colors
    gradient = []
    for i in range(int(steps)):
        # Calculate the RGB values for the current step
        r = int(rgb_start[0] + i * step_size[0])
        g = int(rgb_start[1] + i * step_size[1])
        b = int(rgb_start[2] + i * step_size[2])
        
        # Convert the RGB values to a hexadecimal string
        hex_color = '#' + format(r, '02x') + format(g, '02x') + format(b, '02x')
        
        # Add the hexadecimal color string to the gradient list
        gradient.append(hex_color)
    return gradient

def plot_subfigure_no_uv(surface_points, ax, color, label):
    ax.plot_wireframe(surface_points[:, :, 0],
                                surface_points[:, :, 1],
                                surface_points[:, :, 2],
                                    color=color, label=label[0])
    
    ax.azim = 45
    ax.dist = 6.5
    ax.elev = 30
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_zticks([])
    ax.xaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))
    ax.yaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))
    ax.zaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))
    ax._axis3don = False

def adjust_plot(ax):
    ax.azim = 45
    ax.dist = 6.5
    ax.elev = 30

    ax.set_xlim([-1, 1])
    ax.set_xlim([-1, 1])
    ax.set_xlim([-1, 1])
    ax.set_xlim([-1, 1])
    ax.set_xlim([-1, 1])
    ax.set_xlim([-1, 1])

    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_zticks([])
    ax.xaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))
    ax.yaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))
    ax.zaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))
    ax._axis3don = False

def plot_subfigure(num_ctrl_pts1, num_ctrl_pts2, uspan_uv, vspan_uv, surface_points, ax, colors, ctrlpts, color, label, uvlabel=False):
    u_index = 0
    for i in range(num_ctrl_pts1 - 3):
        u_index += uspan_uv[i + 3]
        v_index = 0
        for j in range(num_ctrl_pts2 - 3):
            if u_index == 512 or v_index == 512 or u_index - uspan_uv[i + 3] == 0 or u_index - uspan_uv[i + 3] == 256:
                if u_index == 512: 
                    ax.plot_wireframe(surface_points[u_index - uspan_uv[i + 3]:-1, v_index:v_index + vspan_uv[j + 3], 0],
                                surface_points[u_index - uspan_uv[i + 3]:-1, v_index:v_index + vspan_uv[j + 3], 1],
                                surface_points[u_index - uspan_uv[i + 3]:-1, v_index:v_index + vspan_uv[j + 3], 2],
                                    color=colors[i * (num_ctrl_pts2 - 3) + j], label = 'u = 1, v = 1' if(uvlabel and v_index + vspan_uv[j + 3] == 512) else None)
                elif v_index == 512:
                    ax.plot_wireframe(surface_points[u_index - uspan_uv[i + 3]:-1, v_index:-1, 0],
                                surface_points[u_index - uspan_uv[i + 3]:-1, v_index:-1, 1],
                                surface_points[u_index - uspan_uv[i + 3]:-1, v_index:-1, 2],
                                    color=colors[i * (num_ctrl_pts2 - 3) + j])
                elif u_index - uspan_uv[i + 3] == 0:
                    ax.plot_wireframe(surface_points[u_index - uspan_uv[i + 3]:u_index, v_index:v_index + vspan_uv[j + 3], 0],
                                    surface_points[u_index - uspan_uv[i + 3]:u_index, v_index:v_index + vspan_uv[j + 3], 1],
                                    surface_points[u_index - uspan_uv[i + 3]:u_index, v_index:v_index + vspan_uv[j + 3], 2],
                                    color=colors[i * (num_ctrl_pts2 - 3) + j], label = 'u = 0, v = 0' if(uvlabel and v_index == 0) else None)
                elif u_index - uspan_uv[i + 3] == 256:
                    ax.plot_wireframe(surface_points[u_index - uspan_uv[i + 3]:u_index, v_index:v_index + vspan_uv[j + 3], 0],
                                surface_points[u_index - uspan_uv[i + 3]:u_index, v_index:v_index + vspan_uv[j + 3], 1],
                                surface_points[u_index - uspan_uv[i + 3]:u_index, v_index:v_index + vspan_uv[j + 3], 2],
                                    color=colors[i * (num_ctrl_pts2 - 3) + j], label = 'u = 0.5, v = 0.5'.format(v_index + vspan_uv[j + 3]) if(uvlabel and v_index + vspan_uv[j + 3] == 256) else None)
            else:
                ax.plot_wireframe(surface_points[u_index - uspan_uv[i + 3]:u_index, v_index:v_index + vspan_uv[j + 3], 0],
                                surface_points[u_index - uspan_uv[i + 3]:u_index, v_index:v_index + vspan_uv[j + 3], 1],
                                surface_points[u_index - uspan_uv[i + 3]:u_index, v_index:v_index + vspan_uv[j + 3], 2],
                                    color=colors[i * (num_ctrl_pts2 - 3) + j])
             
            v_index += vspan_uv[j + 3]

    # ax.plot_wireframe(ctrlpts[:, :, 0], ctrlpts[:, :, 1], ctrlpts[:, :, 2], linestyle='dashdot', color=color,label=label[0])

    ax.azim = 45
    ax.dist = 6.5
    ax.elev = 30
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_zticks([])
    ax.xaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))
    ax.yaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))
    ax.zaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))
    ax._axis3don = False

def plot_diff_subfigure(surface_points, ax):

    ax.plot_wireframe(surface_points[:, :, 0], surface_points[:, :, 1], surface_points[:, :, 2]
                        ,color='#ffc38a', label = 'diff(target-predict)')
    
    ax.azim = 45
    ax.dist = 6.5
    ax.elev = 30
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_zticks([])
    ax.xaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))
    ax.yaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))
    ax.zaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))
    ax._axis3don = False

def chamfer_distance(pred, gt, sqrt=False):
    """
    Computes average chamfer distance prediction and groundtruth
    :param pred: Prediction: B x N x 3
    :param gt: ground truth: B x M x 3
    :return:
    """
    if isinstance(pred, np.ndarray):
        pred = Variable(torch.from_numpy(pred.astype(np.float32))).cuda()

    if isinstance(gt, np.ndarray):
        gt = Variable(torch.from_numpy(gt.astype(np.float32))).cuda()

    pred = torch.unsqueeze(pred, 1)
    gt = torch.unsqueeze(gt, 2)

    diff = pred - gt
    diff = torch.sum(diff ** 2, 3)
    if sqrt:
        diff = guard_sqrt(diff)

    cd = torch.mean(torch.min(diff, 1)[0], 1) + torch.mean(torch.min(diff, 2)[0], 1)
    cd = torch.mean(cd) / 2.0
    return cd

def laplacian_loss_unsupervised(output, dist_type="l2"):
    filter = ([[[0.0, 0.25, 0.0], [0.25, -1.0, 0.25], [0.0, 0.25, 0.0]],
               [[0, 0, 0], [0, 0, 0], [0, 0, 0]],
               [[0, 0, 0], [0, 0, 0], [0, 0, 0]]])

    filter = np.stack([filter, np.roll(filter, 1, 0), np.roll(filter, 2, 0)])

    filter = -np.array(filter, dtype=np.float32)
    filter = Variable(torch.from_numpy(filter)).cuda()
    # print(output.shape)
    laplacian_output = F.conv2d(output.permute(0, 3, 1, 2), filter, padding=1)

    if dist_type == "l2":
        dist = torch.sum((laplacian_output) ** 2, (1,2,3)) 
        # dist = torch.sum((laplacian_output) ** 2, (1,2,3)) + torch.sum((laplacian_input)**2,(1,2,3))
    elif dist_type == "l1":
        dist = torch.abs(torch.sum(laplacian_output.mean(),1))
    dist = torch.mean(dist)

    return dist

# def laplacian_loss_unsupervised(output, dist_type="l2"):
#     filter = torch.tensor([[[0.0, 0.25, 0.0], [0.25, -1.0, 0.25], [0.0, 0.25, 0.0]],
#                            [[0, 0, 0], [0, 0, 0], [0, 0, 0]],
#                            [[0, 0, 0], [0, 0, 0], [0, 0, 0]]], dtype=torch.float32)

#     filter = -torch.stack([filter, torch.roll(filter, 1, 0), torch.roll(filter, 2, 0)])

#     # filter = -filter
#     # filter = filter.to(output.device)

#     laplacian_output = F.conv2d(output.permute(0, 3, 1, 2), filter, padding=1)

#     if dist_type == "l2":
#         dist = torch.sum((laplacian_output) ** 2, (1,2,3)) 
#         # dist = torch.sum((laplacian_output) ** 2, (1,2,3)) + torch.sum((laplacian_input)**2,(1,2,3))
#     elif dist_type == "l1":
#         dist = torch.abs(torch.sum(laplacian_output.mean(),1))
#     dist = torch.mean(dist)

#     return dist

def hausdorff_distance(pred, gt):
    """
    Computes the Hausdorff Distance between two point clouds
    :param pred: Prediction: B x N x 3
    :param gt: ground truth: B x M x 3
    :return: Hausdorff Distance
    """
    batch_size = pred.shape[0]
    pred = torch.unsqueeze(pred, 1)  # B x 1 x N x 3
    gt = torch.unsqueeze(gt, 2)  # B x M x 1 x 3
    # print(pred.shape, gt.shape)
    dist_matrix = torch.sqrt(torch.sum((pred - gt) ** 2, dim=3))  # B x M x N

    row_max, _ = torch.max(torch.min(dist_matrix, dim=2)[0], dim=1)
    col_max, _ = torch.max(torch.min(dist_matrix, dim=1)[0], dim=1)

    hd = torch.max(row_max, col_max)
    hd = torch.mean(hd)
    return hd


def main():
    timing = []
    # load point cloud
    max_coord = min_coord = 0
    resolution = 50
    ctr_pts = 30
    p = q = 4
    with open('meshes/sphere_' + str(resolution * resolution) + '.off', 'r') as f:
        lines = f.readlines()

        # skip the first line
        lines = lines[2:]
        lines = random.sample(lines, k=resolution * resolution)
        # extract vertex positions
        vertex_positions = []
        for line in lines:
            x, y, z = map(float, line.split()[:3])
            min_coord = min(min_coord, x, y, z)
            max_coord = max(max_coord, x, y, z)
            vertex_positions.append((x, y, z))
        range_coord = max(abs(min_coord), abs(max_coord))
        vertex_positions = [(x/range_coord, y/range_coord, z/range_coord) for x, y, z in vertex_positions]
            # vertex_positions.append([x, y, z])
    # print(len(vertex_positions))
    # print(vertex_positions[1])
    print(len(vertex_positions))

    num_ctrl_pts1 = ctr_pts
    num_ctrl_pts2 = ctr_pts
    num_eval_pts_u = resolution
    num_eval_pts_v = resolution

    target = torch.tensor(vertex_positions).reshape(1, num_eval_pts_u, num_eval_pts_v, 3).float().cuda()

    # print(target.shape)
    # PTS = target.detach().numpy().squeeze()
    # Max_size = off.Max_size(np.reshape(PTS, [1, num_eval_pts_u * num_eval_pts_v, 3]))
    inp_ctrl_pts = torch.nn.Parameter(torch.rand((1,num_ctrl_pts1,num_ctrl_pts2,3), requires_grad=True).float().cuda())


    knot_int_u = torch.nn.Parameter(torch.ones(num_ctrl_pts1+p+1-2*p-1).unsqueeze(0).cuda(), requires_grad=True)
    knot_int_v = torch.nn.Parameter(torch.ones(num_ctrl_pts2+q+1-2*q-1).unsqueeze(0).cuda(), requires_grad=True)

    weights = torch.nn.Parameter(torch.ones((1,num_ctrl_pts1,num_ctrl_pts2,1), requires_grad=True).float().cuda())

    # print(target.shape)
    layer = SurfEval(num_ctrl_pts1, num_ctrl_pts2, dimension=3, p=p, q=q, out_dim_u=num_eval_pts_u, out_dim_v=num_eval_pts_v, method='tc', dvc='cuda').cuda()
    opt1 = torch.optim.Adam(iter([inp_ctrl_pts, weights]), lr=0.5) 
    opt2 = torch.optim.Adam(iter([knot_int_u, knot_int_v]), lr=1e-2)
    lr_schedule1 = torch.optim.lr_scheduler.ReduceLROnPlateau(opt1, patience=3)
    lr_schedule2 = torch.optim.lr_scheduler.ReduceLROnPlateau(opt2, patience=3)
    pbar = tqdm(range(10000))
    colors = generate_gradient('#ff0000', '#00ff00', (num_ctrl_pts1 - 3) * (num_ctrl_pts2 - 3) // 2) + generate_gradient('#00ff00', '#0000ff', (num_ctrl_pts1 - 3) * (num_ctrl_pts2 - 3) // 2)
    fig = plt.figure(figsize=(15, 9))
    time1 = time.time()
    for i in pbar:
        # torch.cuda.empty_cache()
        knot_rep_p_0 = torch.zeros(1,p+1).cuda()
        knot_rep_p_1 = torch.zeros(1,p).cuda()
        knot_rep_q_0 = torch.zeros(1,q+1).cuda()
        knot_rep_q_1 = torch.zeros(1,q).cuda()


        def closure():
            opt1.zero_grad()
            opt2.zero_grad()
            # out = layer(inp_ctrl_pts)
            out = layer((torch.cat((inp_ctrl_pts,weights), -1), torch.cat((knot_rep_p_0,knot_int_u,knot_rep_p_1), -1), torch.cat((knot_rep_q_0,knot_int_v,knot_rep_q_1), -1)))

            # loss = ((target-out)**2).mean()
            # loss = 0.1 * laplacian_loss_unsupervised(out)
            loss = 0
            # loss = 0
            loss += 0.1 * laplacian_loss_unsupervised(out)
            out = out.reshape(1, num_eval_pts_u*num_eval_pts_v, 3)
            tgt = target.reshape(1, num_eval_pts_u*num_eval_pts_v, 3)
            # loss += 10 * hausdorff_distance(out, tgt)
            # loss += ((out - tgt) ** 2).mean() #+ 10 * directed_hausdorff(out, tgt)
            loss += chamfer_distance(out, tgt) 
            
            

            loss.backward(retain_graph=True)
            return loss

        if (i%300) < 30:
            loss = opt1.step(closure)
        else:
            loss = opt2.step(closure)        


        out = layer((torch.cat((inp_ctrl_pts,weights), -1), torch.cat((knot_rep_p_0,knot_int_u,knot_rep_p_1), -1), torch.cat((knot_rep_q_0,knot_int_v,knot_rep_q_1), -1)))
        target = target.reshape(1,num_eval_pts_u,num_eval_pts_v,3)
        out = out.reshape(1,num_eval_pts_u,num_eval_pts_v,3)
        
        if loss.item() < 1e-4:
            print((time.time() - time1)/ (i + 1)) 
            break
        
        pbar.set_description("Loss %s: %s" % (i+1, loss.item()))

    print((time.time() - time1)/ (3000)) 

    train_uspan_uv, train_vspan_uv = layer.getuvspan()
    # target_uspan_uv, target_vspan_uv = layer.getuvsapn()
    # print(inp_ctrl_pts)

    target_mpl = target.cpu().numpy().squeeze()
    # target_mpl = target_mpl.reshape(-1, 3)
    # print(out.shape)
    predicted = out.detach().cpu().numpy().squeeze()
    # predicted = predicted.reshape(-1, 3)
    # predictedknotu = utilities.generate_knot_vector(4, num_ctrl_pts1)
    # predictedknotv = utilities.generate_knot_vector(4, num_ctrl_pts2)
    predictedweights = weights.detach().cpu().numpy().squeeze(0)
    predictedctrlpts = inp_ctrl_pts.detach().cpu().numpy().squeeze()
    # print(predictedweights.shape)
    # print(predictedctrlpts.shape)
    predictedknotu = knot_int_u.detach().cpu().numpy().squeeze().tolist()
    predictedknotu = [0., 0., 0., 0., 0.] + predictedknotu + [1., 1., 1., 1.]
    predictedknotv = knot_int_v.detach().cpu().numpy().squeeze().tolist()
    predictedknotv = [0., 0., 0., 0., 0.] + predictedknotv + [1., 1., 1., 1.]

    # Open the file in write mode
    with open('u_test.cpt', 'w') as f:
        # Loop over the array rows
        x = predictedctrlpts
        x = x.reshape(-1, 3)
        for row in x:
            # Flatten the row to a 1D array
            # row_flat = row.reshape(-1, 3)
            # Write the row values to the file as a string separated by spaces
            f.write(' '.join([str(x) for x in row]) + '\n')

    with open('u_test.weights', 'w') as f:
        # Loop over the array rows
        x = predictedweights

        for row in x:
            # Flatten the row to a 1D array
            row_flat = row.reshape(-1)
            # Write the row values to the file as a string separated by spaces
            f.write(','.join([str(x) for x in row_flat]) + '\n')

    with open('u_test.knotu', 'w') as f:
        # Loop over the array rows
        x = predictedknotu

        for row in x:
            # Flatten the row to a 1D array
    
            # Write the row values to the file as a string separated by spaces
            f.write(','.join([str(row)]) + '\n')

    with open('u_test.knotv', 'w') as f:
        # Loop over the array rows
        x = predictedknotv

        for row in x:
            # Flatten the row to a 1D array
   
            # Write the row values to the file as a string separated by spaces
            f.write(','.join([str(row)]) + '\n')


    # ctrlpts = ctrlpts.reshape(num_ctrl_pts1, num_ctrl_pts2, 3)

    # predictedWeight = weights.detach().cpu().numpy().squeeze(0)
    # print(predictedknotu)
    # target_ctrl_pts = torch.from_numpy(np.concatenate([predctrlpts,predictedWeight],axis=-1)).view(1,num_ctrl_pts1,num_ctrl_pts2,4)
    # target_eval_layer = SurfEvalBS(num_ctrl_pts1, num_ctrl_pts2, knot_u=predictedknotu, knot_v=predictedknotv, dimension=3, p=3, q=3, out_dim_u=128, out_dim_v=128)
    # predicted_extended = target_eval_layer(target_ctrl_pts).float().numpy().squeeze(0)
    # predicted_extended = predicted_extended.reshape(-1, 3)
    # print(predicted_extended)
    # print(np.shape(predicted_extended))
    ax1 = fig.add_subplot(141, projection='3d', adjustable='box', proj_type='ortho')
    ax1.set_box_aspect([1,1,1])
    ax1.scatter(target_mpl[:, :, 0], target_mpl[:, :, 1], target_mpl[:, :,2], color='red', label=['GT Surface'])
    adjust_plot(ax1)

    ax2 = fig.add_subplot(142, projection='3d', adjustable='box', proj_type='ortho')
    ax2.set_box_aspect([1,1,1])
    ax2.plot_wireframe(predictedctrlpts[:, :,0], predictedctrlpts[:, :, 1], predictedctrlpts[:, :, 2], color='blue', label=['Predicted Control Points'])
    ax2.scatter(predicted[:, :, 0], predicted[:, :,1], predicted[:, :,2], color='lightgreen', label=['Predicted Surface'])
    adjust_plot(ax2)

    # using training model to plot the surface
    new_layer = SurfEval(num_ctrl_pts1, num_ctrl_pts2, dimension=3, p=4, q=4, out_dim_u=256, out_dim_v=256, method='tc', dvc='cuda').cuda()

    knot_rep_p_0 = torch.zeros(1,p+1).cuda()
    knot_rep_p_1 = torch.zeros(1,p).cuda()
    knot_rep_q_0 = torch.zeros(1,q+1).cuda()
    knot_rep_q_1 = torch.zeros(1,q).cuda()

    predicted_target = new_layer((torch.cat((inp_ctrl_pts,weights), -1), torch.cat((knot_rep_p_0,knot_int_u,knot_rep_p_1), -1), torch.cat((knot_rep_q_0,knot_int_v,knot_rep_q_1), -1)))
    predicted_target = predicted_target.detach().cpu().numpy().squeeze(0).reshape(256, 256, 3)


    # predicted_target_ctrl_pts = torch.from_numpy(np.concatenate([predictedctrlpts, predictedweights],axis=-1)).view(1,num_ctrl_pts1,num_ctrl_pts2,4)
    # # torch.cat((inp_ctrl_pts, weights), dim=3)
    # predicted_target_eval_layer = SurfEvalBS(num_ctrl_pts1, num_ctrl_pts2, knot_u=predictedknotu, knot_v=predictedknotv, dimension=3, p=4, q=4, out_dim_u=256, out_dim_v=256)
    # predicted_target = predicted_target_eval_layer(predicted_target_ctrl_pts).float().cuda()
    # predicted_target = predicted_target.detach().cpu().numpy().squeeze(0).reshape(-1, 256, 256, 3)

    ax3 = fig.add_subplot(143, projection='3d', adjustable='box', proj_type='ortho')
    ax3.set_box_aspect([1,1,1])

    try:
        # ax3.plot_wireframe(predictedctrlpts[:, :, 0], predictedctrlpts[:, :, 1], predictedctrlpts[:, :, 2], color='lightgreen', label=['Predicted Control points'])
        ax3.scatter(predicted_target[:, :, 0], predicted_target[:, :, 1], predicted_target[:, :, 2], color='red')
    except Exception as e:
        print(e)
    adjust_plot(ax3)

    target_mpl = target_mpl.reshape(resolution, resolution, 3)
    predicted = predicted.reshape(resolution, resolution, 3)
    ax4 = fig.add_subplot(144, adjustable='box')
    error_map = (((predicted - target_mpl) ** 2) / target_mpl).sum(-1)

    im4 = ax4.imshow(error_map, cmap='jet', interpolation='none', extent=[0, 128, 0, 128], vmin=-0.001, vmax=0.001)
    # fig.colorbar(im4, shrink=0.4, aspect=5)
    fig.colorbar(im4, shrink=0.4, aspect=5, ticks=[-0.001, 0, 0.001])
    ax4.set_xlabel('$u$')
    ax4.set_ylabel('$v$')
    x_positions = np.arange(0, 128, 20)  # pixel count at label position
    plt.xticks(x_positions, x_positions)
    plt.yticks(x_positions, x_positions)
    ax4.set_aspect(1)

    # ax5 = fig.add_subplot(235, projection='3d', adjustable='box')
    # plot_diff_subfigure(target_mpl - predicted, ax5)

    fig.subplots_adjust(hspace=0, wspace=0)
    fig.tight_layout()
    lines_labels = [ax.get_legend_handles_labels() for ax in fig.axes[:]]
    lines, labels = [sum(lol, []) for lol in zip(*lines_labels)]

    # finally we invoke the legend (that you probably would like to customize...)

    fig.legend(lines, labels, ncol=2, loc='lower left', bbox_to_anchor=(0.33, 0.0), )
    # plt.savefig('ducky_reparameterization_no_ctrpts.pdf')
    plt.savefig('sphere_ctrpts_150_eval_100.pdf')
    plt.show()
    pass

if __name__ == '__main__':
    main()


    